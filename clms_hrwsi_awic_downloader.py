import os
import sys
import logging
import datetime
import argparse
import requests
import geopandas as gpd
from pyogrio.errors import DataSourceError
from shapely import GEOSException
import xml.etree.ElementTree as ET


def str2bool(v):
    """Transforms input string into boolean

    Args:
        v (string): input string value

    Raises:
        argparse.ArgumentTypeError: _description_

    Returns:
        bool: True or False
    """

    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected for requestGeometries parameter.')

def validate_Rfc3339(date_text):
    """Checks the format of the date

    Args:
        date_text (string): input date

    Raises:
        ValueError: _description_

    Returns:
        string: input date if the format matches YYYY-MM-DD
    """

    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
        return date_text
    except:
        raise ValueError("Incorrect date format, should be YYYY-MM-DD")

def format_awic_product(awic, index):
    """Formats a raw AWIC product entry into a structured list

    Args:
        awic (list): A sequence containing raw AWIC product data, including 13 elements
            Exepected format:
            [river_km_id,'YYYYMMDD','HHMMSS',water_perc,ice_perc,other_perc,cloud_perc,shdw_perc,nd_perc,qa,s1_perc,s2_perc,mission_type]
        index (int): index of the products

    Returns:
        list: A list of 13 elements, including
            [id, river_km_id,'YYYY-MM-DDTHH:MM:SS',water_perc,ice_perc,other_perc,cloud_perc,shdw_perc,nd_perc,qa,s1_perc,s2_perc,mission]
    """
    try:
        time_str = f"{awic[2]:06d}"
        observation_datetime = datetime.datetime.strptime(
            f"{awic[1]}T{time_str}", "%Y%m%dT%H%M%S"
        ).strftime('%Y-%m-%dT%H:%M:%S')
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid date/time in AWIC product: {e}")
    
    mission_code = awic[12] if len(awic) > 12 else None
    mission_labels = {
        0: "Sentinel-1 Sentinel-2",
        1: "Sentinel-1",
        2: "Sentinel-2"
    }
    mission = mission_labels.get(mission_code, "")
    
    awic_formatted = [index + 1, awic[0], observation_datetime]
    
    # Append fields 3 to 11 (indexes 3 to 11 inclusive)
    awic_formatted.extend(awic[3:12])

    # Append mission label
    awic_formatted.append(mission)
    
    return awic_formatted

class AwicRequest(object):
    '''
    Request awic products in the catalogue.
    '''

    # Request URL root
    URL_ROOT = 'https://wsi.land.copernicus.eu/awic/'

    # AWIC procedure
    AWIC_PROC = 'get_awic'

    # Geometry procedure
    GEOMETRY_PROC = 'get_geometries'

    # URL parameter: geometry - region of interest, defined as WKT string (POINT, POLYGON, etc.)
    # in EPSG:4326 (WGS84) projection or EPSG:3035(LAEA/ETRS89).
    URL_PARAM_GEOMETRYWKT_WGS84 = 'geometrywkt_wgs84'
    URL_PARAM_GEOMETRYWKT_LAEA = 'geometrywkt_laea'

    # URL parameters: startDate, completionDate - the date limits when the sensing was performed
    URL_PARAM_OBSERVATIONDATE_AFTER = 'startdate'
    URL_PARAM_OBSERVATIONDATE_BEFORE = 'completiondate'

    #URL parameter : cloud
    URL_PARAM_CLOUD_PERCENTAGE = 'cloudcoveragemax'
    
    #URL parameter : output_srid
    URL_PARAM_OUTPUT_SRID_GEOMETRY = 'output_srid'
    
    #URL of metadata
    METADATA_URL = ET.Element("MT_Metadata", url="https://sdi.eea.europa.eu/catalogue/srv/eng/catalog.search#/metadata/5752e8b5-ecda-4013-8eb9-e27f8515b87e")

    def __init__(self, outputDir, returnMode):
        if outputDir is not None:
            self.outputDir = os.path.abspath(outputDir)
            if returnMode != "variable":
                if not os.path.exists(self.outputDir):
                    logging.info("Creating directory " + self.outputDir)
                    os.makedirs(self.outputDir)
                else:
                    logging.warning("Existing directory " + self.outputDir)
        else:
            self.outputDir = None
        self.awic_http_request = None
        self.geometry_http_request = None
        self.awic_result_file = None

    def set_awic_http_request(self, awic_http_request):
        self.awic_http_request = awic_http_request

    def set_geometry_http_request(self, geometry_http_request):
        self.geometry_http_request = geometry_http_request

    def set_awic_result_file(self, awic_result_file):
        self.awic_result_file = awic_result_file

    def build_request(self,
                        startDate=None,
                        completionDate=None,
                        geometrywkt_wgs84=None,
                        geometrywkt_laea=None,
                        cloudCoverageMax=None):
        """Build the request to access HR-S&I catalogue.

        Args:
            startDate (str, optional): Start date in RFC3339 format.. Defaults to None.
            completionDate (str, optional): End date in RFC3339 format.. Defaults to None.
            geometrywkt_wgs84 (str, optional): Geometry in WGS84 WKT format.. Defaults to None.
            geometrywkt_laea (str, optional): Geometry in LAEA WKT format.. Defaults to None.
            cloudCoverageMax (int, optional): Maximum percentage of cloud coverage allowed.. Defaults to None.
        """
        # URL parameters.
        url_params = {}
        if geometrywkt_wgs84 is not None and geometrywkt_laea is not None:
            logging.error("Geometry must be either WGS84 or LAEA (EPSG:3035), not both.")
            sys.exit()
        
        if geometrywkt_wgs84 is not None:
            geometry = geometrywkt_wgs84.replace(',', '%2C').replace(' ', '+')
            url_param_geometry_key = AwicRequest.URL_PARAM_GEOMETRYWKT_WGS84
            output_srid = "wgs84"

        elif geometrywkt_laea is not None:
            geometry = geometrywkt_laea.replace(',', '%2C').replace(' ', '+')
            url_param_geometry_key = AwicRequest.URL_PARAM_GEOMETRYWKT_LAEA
            output_srid = "laea"

        else:
            logging.error("Geometry must be specified (either geometrywkt_wgs84 ou geometrywkt_laea).")
            sys.exit()

        url_params[url_param_geometry_key] = geometry

        if cloudCoverageMax:
            url_params[AwicRequest.URL_PARAM_CLOUD_PERCENTAGE] = cloudCoverageMax
        if startDate:
            url_params[AwicRequest.URL_PARAM_OBSERVATIONDATE_AFTER] = \
                validate_Rfc3339(startDate)
        if completionDate:
            url_params[AwicRequest.URL_PARAM_OBSERVATIONDATE_BEFORE] = \
                validate_Rfc3339(completionDate)


        if(url_params):
            self.set_awic_http_request(AwicRequest.URL_ROOT + AwicRequest.AWIC_PROC + \
                      '?' + \
                      '&'.join(['%s=%s'%(key, value) for key, value in url_params.items()])
            )

            self.set_geometry_http_request(AwicRequest.URL_ROOT + AwicRequest.GEOMETRY_PROC + \
                      '?' + f'{url_param_geometry_key}={geometry}&{AwicRequest.URL_PARAM_OUTPUT_SRID_GEOMETRY}={output_srid}'
            )

        else:
            logging.error("No query parameters were provided, no query was generated")
            sys.exit()


    def execute_request(self, returnMode, request_geometries=False):
        """Executes the AWIC and geometry HTTP requests, retrieves and optionally saves data.

        Args:
            returnMode (str): Mode of return, must be one of 'csv', 'variable', or 'csv_and_variable'.
            request_geometries (bool, optional): Whether to retrieve geometries. Defaults to False.

        Returns:
            tuple: (geometries, awic_products) or (None, None) depending on returnMode.
        """
        # Check that the request was set before the call
        if self.awic_http_request is None:
            logging.error("No awic_http_request was provided or configured")
            sys.exit()
            
        if self.geometry_http_request is None:
            logging.error("No geometry_http_request was provided or configured")
            sys.exit()

        # Request geometry
        if request_geometries:
            geometries = self.request_geometry(
                self.geometry_http_request,
                returnMode,
                geometriesPath=self.outputDir
            )
        else:
            geometries = None

        # Request AWIC products
        awic_products = self.request_page(self.awic_http_request)
        if len(awic_products) == 0:
            logging.warning("No AWIC data was found")
        else:
            logging.info(f"Found {len(awic_products)} AWIC products.")

        # Save AWIC results to CSV if needed
        if returnMode in ('csv', 'csv_and_variable'):
            self.set_awic_result_file(os.path.join(self.outputDir, "awic.csv"))
            logging.info(f"Writing AWIC data to {self.awic_result_file}")
            try:
                with open(self.awic_result_file, 'w') as f:
                    f.write(
                        'id;geometries_id;datetime;water_perc;ice_perc;other_perc;cloud_perc;shdw_perc;nd_perc;qa;s1_perc;s2_perc;source\n'
                    )
                    for p in awic_products:
                        line = ';'.join(str(x) for x in p) + '\n'
                        f.write(line)
            except IOError as e:
                logging.error(f"Error writing AWIC CSV file: {e}")
                sys.exit()


        # Write metadata XML file
        if returnMode in ('csv', 'csv_and_variable'):
            mtd_path = os.path.join(self.outputDir, "AWIC_MTD.xml")
            logging.info(f"Writing metadata link into {mtd_path}")
            try:
                with open(os.path.join(self.outputDir, "AWIC_MTD.xml"), 'w') as f:
                    f.write(ET.tostring(AwicRequest.METADATA_URL, encoding='utf8', method='xml').decode())
                    f.close()
            except IOError as e:
                logging.error(f"Error writing metadata XML: {e}")
                sys.exit()

        if returnMode == 'csv':
            return None, None
            
        return geometries, awic_products


    def request_geometry(self, http_request, returnMode, geometriesPath = None):
        """Sends an HTTP request to retrieve geometry information from the API.

        Args:
            http_request (str): The full URL of the HTTP request to be executed.
            returnMode (str): One of 'csv', 'variable', or 'csv_and_variable'.
            request_geometries (bool, optional): Whether to extract and return geometries. Defaults to False.
            geometriesPath (str, optional): Directory to save CSV output if returnMode requires it.. Defaults to None.

        Returns:
            list: A list of geometry entries if request_geometries is True, otherwise an empty list.
        """
        logging.info(f'Executing request for geometries: {http_request}')
        
        try:
            response = requests.get(http_request)
        except requests.RequestException as e:
            logging.error(f"HTTP request failed: {e}")
            sys.exit(500)
            
        if response.status_code == 414:
            logging.error('Request-URI Too Large')
            sys.exit(500)
        
        try:
            json_root = response.json()
        except ValueError:
            logging.error("Failed to parse JSON response")
            sys.exit(500)

        if isinstance(json_root, dict) and json_root.get('code') == '0100E':
            logging.error(f"API returned error: {json_root.get('message')}")
            sys.exit(413)
            
        geometries = []
        
        for item in json_root:
            geom = item.get('j')
            if geom:
                geometries.append(geom)
        
        if returnMode in ('csv', 'csv_and_variable'):
            if not geometriesPath:
                logging.error("Geometries path must be provided for CSV output.")
                sys.exit(500)
            output_file = os.path.join(geometriesPath, "geometries.csv")
            logging.info(f"Writing geometries to {output_file}")
            try:
                with open(output_file, 'w', encoding='utf8') as f:
                    f.write('id;geometry;basin_name;eu_hydro_id;object_nam;area;river_km\n')
                    for p in geometries:
                        line = ';'.join(str(x) for x in p) + '\n'
                        f.write(line)
            except IOError as e:
                logging.error(f"Failed to write geometries file: {e}")
                sys.exit(500)

        return geometries


    def request_page(self, http_request):
        """ Sends an HTTP GET request to retrieve a page of AWIC products and formats them.

        Args:
            http_request (str):  The full URL of the HTTP request.

        Returns:
            list: A list of formatted AWIC products.
        """

        # Send Get request
        logging.info('Executing request for AWIC: %s'%http_request)
        
        try:
            response = requests.get(http_request, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during HTTP request: {e}")
            return []

        # Read JSON response
        try:
            json_root = response.json()
        except ValueError:
            logging.error("Error: Response content is not valid JSON.")
            return []

        # Extract and format AWIC products
        awic_products = []
        for i, item in enumerate(json_root):
            raw_awic = item.get('j')
            if raw_awic:
                formatted = format_awic_product(raw_awic, i)
                awic_products.append(formatted)

        return awic_products


def download_awic_products(returnMode, outputDir=None, startDate=None, completionDate=None, geometrywkt_wgs84=None, geometrywkt_laea=None, cloudCoverageMax=None, requestGeometries=False):
    """Downloads AWIC products based on the given criteria and return mode.

    Args:
        returnMode (str): 'csv', 'csv_and_variable', or 'variable'.
        outputDir (str, optional): Directory where outputs will be saved.. Defaults to None.
        startDate (str, optional): Start date in RFC3339 format.. Defaults to None.
        completionDate (str, optional): End date in RFC3339 format.. Defaults to None.
        geometrywkt_wgs84 (str, optional): Geometry in WGS84 WKT format.. Defaults to None.
        geometrywkt_laea (str, optional): Geometry in LAEA WKT format.. Defaults to None.
        cloudCoverageMax (int, optional): Maximum percentage of cloud coverage allowed.. Defaults to None.
        requestGeometries (bool, optional): Whether to retrieve geometries.. Defaults to False.

    Returns:
        tuple: (geometries, awic_products) or (None, None) depending on returnMode.
    """
    valid_modes = {'csv', 'csv_and_variable', 'variable'}
    if returnMode not in valid_modes:
        raise ValueError(f"Invalid returnMode: {returnMode}. Must be one of {valid_modes}")

    if returnMode in {'csv', 'csv_and_variable'} and outputDir is None:
        raise ValueError("outputDir must be specified for csv and csv_and_variable return modes")

    awic = AwicRequest(outputDir, returnMode)

    # Build URL request
    awic.build_request(
        startDate=startDate,
        completionDate=completionDate,
        geometrywkt_wgs84=geometrywkt_wgs84,
        geometrywkt_laea=geometrywkt_laea,
        cloudCoverageMax=cloudCoverageMax
    )

    # Query HTTP API to list results
    geometries, awic_products = awic.execute_request(
        returnMode,
        request_geometries=requestGeometries
    )

    logging.info("End of AWIC download.")

    return geometries, awic_products

def validate_file(geometry_file):
        '''
        Makes sure that the vector file exists and is valid
        '''
        try:
            test_gpd = gpd.read_file(geometry_file)
        except DataSourceError as err:
            logging.error(f"-geometry_file : {err}")
            sys.exit()
        except ValueError as err:
            logging.error(f"-geometry_file : {err}")
            sys.exit()
        except GEOSException as err:
            logging.error(f"-geometry_file : {err}")
            sys.exit()

        test_wkt = str(test_gpd.union_all())
        test_epsg = test_gpd.crs.to_epsg()

        return test_epsg,test_wkt

def validate_wkt_epsg(epsg_text,wkt_text):
    '''
    Makes sure that the epsg and wkt are in the right formats
    '''
    try:
        wkt_geo = gpd.GeoSeries.from_wkt([wkt_text],crs=epsg_text)
    except CRSError as e:
        logging.error(f"-epsg : {e}")
        sys.exit()
    except GEOSException as e:
        logging.error(f"-wkt : {e}")
        sys.exit()

    if wkt_geo.geom_type.item() not in ['MultiPolygon','Polygon','Point']:
        logging.error(f"-wkt : only Polygon or MultiPolygon is accepted")
        sys.exit()

    return epsg_text,wkt_text

if __name__ == "__main__":
    # Set logging level and format.
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format= \
        '%(asctime)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="""This script can be used to request AWIC statistics, see the example below:\n
    > python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output -geometrywkt_wgs84 "POINT(22.457940 49.367854)" -startDate 2025-01-15 -completionDate 2025-01-25 -requestGeometries True\n""", formatter_class=argparse.RawTextHelpFormatter)

    # Parameters used to define a query, or to build a new one
    group_query = parser.add_argument_group("query_params", "mandatory parameters for query")
    group_query.add_argument("-returnMode",type=str, required=True, default='csv', help="Specify whether the return should be stored in a CSV file, a python variable, or both (csv|variable|csv_and_variable). Default value is 'csv'.")
    group_query.add_argument("-startDate", type=str, required=True, help="Start date in format YYYY-MM-DD")
    group_query.add_argument("-completionDate", type=str, required=True, help="End date in format YYYY-MM-DD")
    
    group_query = parser.add_argument_group("query_params", "optional parameters for query")
    group_query.add_argument("-outputDir",type=str, required=False, default=None, help="Output directory to store AWIC data, required if returnMode is csv or csv_and_variable")
    group_query.add_argument("-cloudCoverageMax", type=str, required=False, default=100, help="Maximum percentage of cloud or cloud shadow data between 0 and 100. Default value is 100.")
    group_query.add_argument("-requestGeometries", type=str, required=False, default='False', help="Boolean to indicate if the geometries should be retrieved (true|false). Default value is False.")

    group_mode_s = parser.add_argument_group("selection mode")
    group_mode_sel = group_mode_s.add_mutually_exclusive_group()
    group_mode_sel.add_argument("-geometrywkt_wgs84", type=str, help="WKT geometry in World Geodetic System 1984 / WGS84 (EPSG:4326) coordinate system as text to specify the desired location")
    group_mode_sel.add_argument("-geometrywkt_laea", type=str, help="WKT geometry in ETRS89-extended - Lambert Azimuthal Equal-Area (LAEA) (EPSG:3035) coordinate system as text to specify the desired location")
    group_mode_sel.add_argument("-geometry_file", type=str, help="Vector file containing 2D vector layers (polygon or multipolygon). Can be .shp, .geojson, .gpkg, .kml. Must include a projection system (either EPSG:3035 or EPSG:4326).")

    args = parser.parse_args()

    #Read geometry_file and fill geometrywkt_wgs84 or geometrywkt_laea according to the projection system given by the user
    if args.geometry_file:
        file_epsg, file_wkt = validate_file(args.geometry_file)
        validate_wkt_epsg(file_epsg, file_wkt)
        if str(file_epsg) == "3035":
            geometrywkt_laea = file_wkt
            geometrywkt_wgs84 = None
        elif str(file_epsg) == "4326":
            geometrywkt_wgs84 = file_wkt
            geometrywkt_laea = None
        else:
            logging.error("EPSG from your input file must be 3035 or 4326")
            sys.exit("-2")

    if args.geometrywkt_laea:
        _, geometrywkt_laea = validate_wkt_epsg("3035",args.geometrywkt_laea)
        geometrywkt_wgs84 = None

    if args.geometrywkt_wgs84:
        _, geometrywkt_wgs84 = validate_wkt_epsg("4326",args.geometrywkt_wgs84)
        geometrywkt_laea = None

    download_awic_products(args.returnMode,
            outputDir=args.outputDir,
            startDate=args.startDate,
            completionDate=args.completionDate,
            geometrywkt_wgs84=geometrywkt_wgs84,
            geometrywkt_laea=geometrywkt_laea,
            cloudCoverageMax=args.cloudCoverageMax,
            requestGeometries=str2bool(args.requestGeometries))

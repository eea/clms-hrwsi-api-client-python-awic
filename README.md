# Python client for accessing the Copernicus Land Monitoring Service - High Resolution Water, Snow & Ice (HR-WSI) products

## Description
Python client for accessing the Copernicus Land Monitoring Service HR-WSI Aggregated Water and Ice Cover (AWIC) data by means of an API. AWIC description can be found in https://sdi.eea.europa.eu/catalogue/srv/api/records/5752e8b5-ecda-4013-8eb9-e27f8515b87e/formatters/xsl-view?output=pdf&language=eng&approved=true

The other Pan-European water, snow and ice products by the CLMS are reachable through the Python client https://github.com/eea/clms-hrwsi-api-client-python 

This script allows to easily download AWIC products over the EEA38+UK area.

## Contact
Copernicus Land Monitoring Service service desk: https://land.copernicus.eu/en/contact-service-helpdesk

## Registration
Data are accessible without any registration.

## Installation
[Prerequistes] Install Conda (https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html)

A Python environment is needed with the packages described in the _env.yaml_ file:
```S
conda env create -f env.yaml # to create a new Python environment with Conda
```

The environment is called _hrwsi-awic-downloader_. It has to be activated. :
```S
conda activate hrwsi-awic-downloader
```
The environment can be removed with `conda deactivate hrwsi-awic-downloader` and called later with `conda activate hrwsi-awic-downloader`.


Download the Python script and run (use correct path):
```S
python clms_hrwsi_awic_downloader.py --help
```
  
## Examples 
For using the script in a terminal:
```S
> python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output_wgs84 -geometrywkt_wgs84 "POINT(22.457940 49.367854)" -startDate 2025-01-15 -completionDate 2025-01-25 -requestGeometries True
> python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output_laea -geometrywkt_laea "POINT(5221056.217256069 2993730.4013467054)" -startDate 2025-01-15 -completionDate 2025-01-25 -cloudCoverageMax 90 -requestGeometries False
> python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output_gpkg -geometry_file geometry.gpkg  -startDate 2025-01-15 -completionDate 2025-01-25 -requestGeometries True
> python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output_geojson -geometry_file geometry.geojson  -startDate 2025-01-15 -completionDate 2025-01-25 -requestGeometries False
> python clms_hrwsi_awic_downloader.py -returnMode csv -outputDir output_shp -geometry_file geometry.shp  -startDate 2025-01-15 -completionDate 2025-01-25 -cloudCoverageMax 90 -requestGeometries True
```
For using the script directly in a Python environment and get the results as a Python variable:
```S
> python
>>> from clms_hrwsi_awic_downloader import download_awic_products
>>> returnMode = 'variable'
>>> outputDir = 'path/to/directory'
>>> startDate = '2025-01-16'
>>> completionDate = '2025-01-17'
>>> geometrywkt_wgs84 = "POINT(2.640786074902044 44.73811271596091)"
>>> cloudCoverageMax = 95
>>> requestGeometries = True
>>> geometries, awic = download_awic_products(returnMode, outputDir=outputDir, startDate=startDate, completionDate=completionDate, geometrywkt_wgs84=geometrywkt_wgs84, geometrywkt_laea=None, cloudCoverageMax=cloudCoverageMax, requestGeometries=requestGeometries)
```

## API URL
To request AWIC statistics, the url to use is the following "https://wsi.land.copernicus.eu/awic/". It must be accompanied by several arguments. 
Eg: https://wsi.land.copernicus.eu/awic/get_awic?startdate=2025-01-15&completiondate=2025-01-25&cloudcoveragemax=100&euhydroid=NONE&geometrywkt_wgs84=POINT%2822.457940%2049.367854%29&geometrywkt_laea=POLYGON%28%29&basinname=NONE&objectname=NONE&getonlysize=false


To request the description of the geometries on which AWIC statistics are computed, the url to use if the following "https://wsi.land.copernicus.eu/awic/". It must be accompanied by several arguments. 
Eg.: https://wsi.land.copernicus.eu/awic/get_geometries?geometrywkt_wgs84=POINT%2822.457940%2049.367854%29&geometrywkt_laea=POLYGON%28%29&euhydroid=NONE&basinname=NONE&objectname=NONE&output_srid=laea&getonlyids=false


Users are invited to consult the ICE products user manual available on the Copernicus land portal for details on the arguments and on how to use the API.

## Legal notice about Copernicus Data
Access to data is based on a principle of full, open and free access as established by the Copernicus data and information policy Regulation (EU) No 1159/2013 of 12 July 2013. This regulation establishes registration and licensing conditions for GMES/Copernicus users and can be found here: http://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32013R1159.  

Free, full and open access to this data set is made on the conditions that:  
1. When distributing or communicating Copernicus dedicated data and Copernicus service information to the public, users shall inform the public of the source of that data and information.  
2. Users shall make sure not to convey the impression to the public that the user's activities are officially endorsed by the Union.  
3. Where that data or information has been adapted or modified, the user shall clearly state this.  
4. The data remain the sole property of the European Union. Any information and data produced in the framework of the action shall be the sole property of the European Union. Any communication and publication by the beneficiary shall acknowledge that the data were produced “with funding by the European Union”.

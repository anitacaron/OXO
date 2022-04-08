#!/bin/bash

set -e
SECONDS=0

############ Runtime variables ############
DOCKERCMD=${DOCKERCMD:-docker}
# You can set DOCKERCOMPOSE to something like export DOCKERCOMPOSE="docker-compose -f /path/to/compose/compose/docker-compose.yml"
DOCKERCOMPOSE=${DOCKERCOMPOSE:-docker-compose}

# The directory where all the non-docker volumes will be persisted, and where the config files are located
VOLUMEROOT=${VOLUMEROOT:-$(pwd)}

# The location of the configuration directory (by default same directory as where the volumes are persisted)
OXOCONFIGDIR=${CONFIGDIR:-$VOLUMEROOT/config}

# The name of the network, as defined by docker-compose
NETWORK=${NETWORK:-host}

##############################################
############ Docker Configuration ############
##############################################

DOCKERRUN=$DOCKERCMD" run"

############ Volumes #########################
NEO4J_IMPORT_DIR=$VOLUMEROOT/oxo-neo4j-import
# The location of the configuration directory (by default same directory as where the volumes are persisted)
OXOCONFIGDIR=${CONFIGDIR:-$VOLUMEROOT/config/}


############ Images ###########################
EBISPOT_OXOLOADER=ihcc/oxo-loader
EBISPOT_OXOINDEXER=ihcc/oxo-indexer:0.0.5

######## Solr Services ########################
OXO_SOLR=http://oxo-solr:8983/solr


##############################################
############ Pipeline ########################
##############################################

# We decided to expose the neo4j import directory for OxO as a local directory, because it is very useful for debugging 
# (checking the generated mapping tables etc). All other volumes are created and managed by docker-compose
echo "WARNING: Removing all existing indexed data"
rm -rfv "$NEO4J_IMPORT_DIR" 
mkdir -vp "$NEO4J_IMPORT_DIR"


# 1. Make sure the OLS/OXO instances are currently not running, or if so, shut them down.
# Note that during development, we are using the `-v` option to ensure that unused volumes are cleared as well.
# https://docs.docker.com/compose/reference/down/
echo "INFO: Shutting any running services down... ($SECONDS sec)"
$DOCKERCOMPOSE down -v

# 5. Now, we start the remaining services. It is important that ols-web is not running at indexing time. 
# This is a shortcoming in the OLS archticture and will likely be solved in future versions
echo "INFO: Firing up remaining services (oxo-solr, oxo-neo4j, oxo-web)... ($SECONDS sec)"
$DOCKERCOMPOSE up -d solr neo4j oxo-web
sleep 100 # Giving the services some time to start. 
# Note, in some environments, 50 seconds may not be sufficient; errors revolving around
# failed connections indicate that you should have waited longer. In that case, increase the sleep time, or better yet, implement a health check before proceeding.

# 6. Now we are extracting the datasets directly from OLS; this basically works on the assumption 
# that the loaded data dictionaries contain the appropriate xrefs (see Step 8). The output of this process is datasources.csv
# which should be in the directory that is mounted to `/mnt/neo4j` (at the time of documentation: $NEO4J_IMPORT_DIR).
echo "INFO: OXO - Extract datasets... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$OXOCONFIGDIR"/idorg.xml:/mnt/idorg.xml \
    -v "$NEO4J_IMPORT_DIR":/mnt/neo4j \
    --network "$NETWORK" \
    -it "$EBISPOT_OXOLOADER" python /opt/oxo-loader/OlsDatasetExtractor.py -c /mnt/config.ini -i /mnt/idorg.xml -d /mnt/neo4j/datasources.csv

# 7. This process loads the datasets declared in the datasources.csv file into the Oxo internal neo4j instance, but nothing else (not the mappings)
echo "INFO: OXO - Load datasets... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/var/lib/neo4j/import \
    --network "$NETWORK" \
    -it "$EBISPOT_OXOLOADER" python /opt/oxo-loader/OxoNeo4jLoader.py -c /mnt/config.ini -W -d datasources.csv

# 8. This process extracts the xref mappings from OLS and exports them into OxO format.
# The result of this process are the two files terms.csv and mappings.csv
echo "INFO: OXO - Extract mappings... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/mnt/neo4j \
    --network "$NETWORK" \
    -it $EBISPOT_OXOLOADER python /opt/oxo-loader/OlsMappingExtractor.py -c /mnt/config.ini -t /mnt/neo4j/terms.csv -m /mnt/neo4j/mappings.csv

# 9. This process finally loads the mappings into Neo4j.
echo "INFO: OXO - Load mappings... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/var/lib/neo4j/import \
    --network "$NETWORK" \
    -it $EBISPOT_OXOLOADER python /opt/oxo-loader/OxoNeo4jLoader.py -c /mnt/config.ini -t terms.csv -m mappings.csv

# 10. Finally, the mappings are indexed in SOLR.
echo "INFO: OXO - Index mappings... ($SECONDS sec)"
$DOCKERRUN --network "$NETWORK" \
           -e spring.data.solr.host=$OXO_SOLR \
           -e oxo.neo.uri=http://neo4j:dba@oxo-neo4j:7474 $EBISPOT_OXOINDEXER


echo "INFO: Redploying Custom OXO pipeline completed in $SECONDS seconds!"
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
OXOCONFIGDIR=${CONFIGDIR:-$VOLUMEROOT/config/}

# The name of the network, as defined by docker-compose
NETWORK=${NETWORK:-customolsnet}

##############################################
############ Docker Configuration ############
##############################################

DOCKERRUN=$DOCKERCMD" run"

############ Volumes #########################
NEO4J_IMPORT_DIR=$VOLUMEROOT/oxo-neo4j-import
OLS_NEO4J_DATA=$VOLUMEROOT/ols-neo4j-data
OLS_NEO4J_DOWNLOADS=$VOLUMEROOT/ols-downloads

############ Images ###########################
EBISPOT_OXOLOADER=ihcc/oxo-loader:0.0.2
EBISPOT_OXOINDEXER=ihcc/oxo-indexer:0.0.2

######## Solr Services ########################
OXO_SOLR=http://solr:8983/solr


##############################################
############ Pipeline ########################
##############################################

# We decided to expose the neo4j import directory for OxO as a local directory, because it is very useful for debugging 
# (checking the generated mapping tables etc). All other volumes are created and managed by docker-compose
echo "WARNING: Removing all existing indexed data"
rm -rfv "$NEO4J_IMPORT_DIR" 
mkdir -vp "$NEO4J_IMPORT_DIR"


# 1. Make sure the OXO instances are currently not running, or if so, shut them down.
# Note that during development, we are using the `-v` option to ensure that unused volumes are cleared as well.
# https://docs.docker.com/compose/reference/down/
echo "INFO: Shutting any running services down... ($SECONDS sec)"
$DOCKERCOMPOSE down -v

# 5. Start the services.
echo "INFO: Firing up remaining services (oxo-solr, oxo-neo4j, oxo-web)... ($SECONDS sec)"
$DOCKERCOMPOSE up -d solr neo4j oxo-web
sleep 50 # Giving the services some time to start. 
# Note, in some environments, 50 seconds may not be sufficient; errors revolving around
# failed connections indicate that you should have waited longer. In that case, increase the sleep time, or better yet, implement a health check before proceeding.

# 9. This process extract metadata from sssom table.
echo "INFO: OXO - Extracting metadata... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/mnt/neo4j \
    --network "$NETWORK" \
    -it $EBISPOT_OXOLOADER python /opt/oxo-loader/OxoNeo4jLoader.py -c /mnt/config.ini -p /mnt/neo4j/ecto.sssom.tsv -m /mnt/neo4j/ecto.sssom.yaml

# 10. This process loads the mappings into Neo4j.
echo "INFO: OXO - Load mappings... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/var/lib/neo4j/import \
    --network "$NETWORK" \
    -it $EBISPOT_OXOLOADER python /opt/oxo-loader/OxoNeo4jLoader.py -c /mnt/config.ini -s ecto.sssom.tsv -m ecto.sssom.yaml

# 11. Finally, the mappings are indexed in SOLR.
echo "INFO: OXO - Index mappings... ($SECONDS sec)"
$DOCKERRUN --network "$NETWORK" \
           -e spring.data.solr.host=$OXO_SOLR \
           -e oxo.neo.uri=http://neo4j:dba@neo4j:7474 $EBISPOT_OXOINDEXER


echo "INFO: Redploying Custom OXO pipeline completed in $SECONDS seconds!"
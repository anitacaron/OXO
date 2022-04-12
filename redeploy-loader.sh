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


############ Images ###########################
EBISPOT_OXOLOADER=ihcc/oxo-loader:0.0.2
EBISPOT_OXOINDEXER=ihcc/oxo-indexer:0.0.5

######## Solr Services ########################
OXO_SOLR=http://oxo-solr:8983/solr

##############################################
############ Pipeline ########################
##############################################

echo "INFO: OXO - Extract mappings... ($SECONDS sec)"
$DOCKERRUN -v "$OXOCONFIGDIR"/config.ini:/mnt/config.ini \
    -v "$NEO4J_IMPORT_DIR":/mnt/neo4j \
    --network "$NETWORK" \
    -it $EBISPOT_OXOLOADER python /opt/oxo-loader/OlsMappingExtractor.py -c /mnt/config.ini -t /mnt/neo4j/terms.csv -m /mnt/neo4j/mappings.csv

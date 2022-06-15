#!/usr/bin/env python
"""
Script for loading large amount sof data in OxO formatted CSV files into a OxO Neo4j.
You can delete the neo4j database, load datasoruces, terms and mapping files with this script
"""
__author__ = "jupp"
__license__ = "Apache 2.0"
__date__ = "03/03/2018"

import re
from neo4j import GraphDatabase, basic_auth
from configparser import ConfigParser
from optparse import OptionParser
import pandas as pd
from urllib.request import urlopen
import yaml
from datetime import date
import json

class Neo4jOxOLoader:
    def __init__(self):
        # if len(sys.argv) != 2:
        #     print "\nNot enough arguments! Please pass a (path) of a config file!"
        #     raise Exception("Not enough arguments! Please pass in a config file!")
        # else:
        #     config = ConfigParser()
        #     config.read(sys.argv[1])

        parser = OptionParser()
        parser.add_option("-s","--sssom", help="load the sssom file")
        parser.add_option("-p","--preprocess", help="preprocess the sssom file")
        parser.add_option("-m", "--metadata", help="file path to save metadata from sssom table")
        parser.add_option("-W","--wipe", action="store_true", dest="wipe", help="wipe the neo4j database")
        parser.add_option("-c","--config", help="config file", default="config.ini")

        options, _ = parser.parse_args()

        config = ConfigParser()
        config.read(options.config)

        try:
            uri = config.get("Basics", "neoURL")
        except:
            print("No config found, please supply a config.ini using -c")
            exit (1)
        neo_user = config.get("Basics", "neoUser")
        neo_pass = config.get("Basics", "neoPass")

        driver = GraphDatabase.driver(uri, auth=basic_auth(neo_user, neo_pass), encrypted=False)
        self.session = driver.session()

        self.session.run("CREATE CONSTRAINT ON (i:Term) ASSERT i.curie IS UNIQUE")
        self.session.run("CREATE CONSTRAINT ON (i:Datasource) ASSERT i.prefix IS UNIQUE")

        if options.wipe:
            while self.deleteMappings() > 0:
                print("Still deleting...")
            print("Mappings deleted!")

            while self.deleteSourceRels() > 0:
                print("Still deleting...")
            print("Source rels deleted!")

            while self.deleteTerms() > 0:
                print("Still deleting...")
            print("Terms deleted!")

            while self.deleteDatasources() > 0:
                print("Still deleting...")
            print("Datasources deleted!")

        if options.preprocess:
          self.preprocess(options.preprocess, options.metadata)
        if options.sssom:
            self.load_datasources(options.sssom)
            self.load_terms(options.sssom)
            self.load_mappings(options.sssom)


    def deleteMappings(self):
        result = self.session.run("match (t)-[m:MAPPING]->() WITH m LIMIT 50000 DETACH DELETE m RETURN count(*) as count")
        for record in result:
            return record["count"]

    def deleteSourceRels(self):
        result = self.session.run("match (t)-[m:HAS_SOURCE]->()  WITH m LIMIT 50000 DETACH DELETE m RETURN count(*) as count")
        for record in result:
            return record["count"]

    def deleteTerms(self):
        result = self.session.run("match (t:Term) WITH t LIMIT 50000 DETACH DELETE t RETURN count(*) as count")
        for record in result:
            return record["count"]

    def deleteDatasources(self):
        result = self.session.run("match (d:Datasource) WITH d LIMIT 1000 DETACH DELETE d RETURN count(*) as count")
        for record in result:
            return record["count"]

    def load_terms(self, terms):
        print("Loading terms from "+terms+"...")

        load_subject_terms_cypher = """
            USING PERIODIC COMMIT 10000 LOAD CSV WITH HEADERS FROM 'file:///"""+terms+"""' AS row
            FIELDTERMINATOR '\t'
            WITH row
            MERGE (t1:Term { curie: row.subject_id})
            SET t1.id = row.subject_identifier, t1.uri = row.subject_uri
            SET t1.label = CASE trim(row.subject_label) WHEN "" THEN null ELSE row.subject_label END
            SET t1.category = CASE trim(row.subject_category) WHEN "" THEN null ELSE row.subject_category END
            WITH row
            MERGE (t2:Term { curie: row.object_id})
            SET t2.id = row.object_identifier, t2.uri = row.object_uri
            SET t2.label = CASE trim(row.object_label) WHEN "" THEN null ELSE row.object_label END
            SET t2.category = CASE trim(row.object_category) WHEN "" THEN null ELSE row.object_category END
        """

        load_terms_souce_cypher = """
          USING PERIODIC COMMIT 10000 LOAD CSV WITH HEADERS FROM 'file:///"""+terms+"""' AS row
          FIELDTERMINATOR '\t'
          MATCH (t1:Term { curie: row.subject_id}), (t2:Term { curie: row.object_id})
          MATCH (d1:Datasource { prefix: row.subject_source}), (d2:Datasource { prefix: row.object_source})
          MERGE (t1)-[:HAS_SOURCE]->(d1)
          MERGE (t2)-[:HAS_SOURCE]->(d2)
        """

        result = self.session.run(load_subject_terms_cypher)
        print(result.consume())
        result = self.session.run(load_terms_souce_cypher)
        print(result.consume())        

    def load_mappings(self, mappings):
        print("Loading mappings from "+mappings+"...")
        load_mappings_cypher = """
            USING PERIODIC COMMIT 10000 LOAD CSV WITH HEADERS FROM 'file:///"""+mappings+"""' AS row
            FIELDTERMINATOR '\t'
            WITH row
            MATCH (subject:Term { curie : row.subject_id}), (object:Term { curie: row.object_id})
            MERGE (subject)-[m:MAPPING { sourcePrefix: row.subject_source, datasource: row.datasource, sourceType: "ONTOLOGY", scope: row.scope, date: row.mapping_date}]->(object)
          """

        result = self.session.run(load_mappings_cypher)
        print(result.consume())

    def load_datasources(self, datasources):
        print("Loading datasources from " + datasources + " ...")
        load_datasources_cypher = """
            LOAD CSV WITH HEADERS FROM 'file:///"""+datasources+"""' AS row
            FIELDTERMINATOR '\t'
            WITH row
            MERGE (d1:Datasource {prefix: row.subject_source})
            MERGE (d2:Datasource {prefix: row.object_source})
            WITH d1, d2, row
            SET d1.preferredPrefix = row.subject_source, d1.name = row.subject_source, d1.description = "", d1.versionInfo = "", d1.idorgNamespace = toLower(row.subject_source), d1.licence = "", d1.sourceType = "ONTOLOGY", d1.alternatePrefix = split(row.subject_source,",")
            SET d2.preferredPrefix = row.object_source, d2.name = row.subject_source, d2.description = "", d2.versionInfo = "", d2.idorgNamespace = toLower(row.object_source), d2.licence = "", d2.sourceType = "ONTOLOGY", d2.alternatePrefix = split(row.object_source, ",")
        """
        # WITH d, line
        #SET d.preferredPrefix = line.prefix, d.name = line.title, d.description = line.description, d.versionInfo = line.versionInfo, d.idorgNamespace = line.idorgNamespace, d.licence = line.licence, d.sourceType = line.sourceType, d.alternatePrefix = split(line.alternatePrefixes,",")
        self.session.run(load_datasources_cypher)

    def preprocess(self, mapping_path, metadata_path):
      sssom = 'https://raw.githubusercontent.com/EnvironmentOntology/environmental-exposure-ontology/master/mappings/ecto.sssom.tsv'
      
      sssom_metadata = self._read_metadata_from_table(sssom)
      
      df = pd.read_csv(sssom, sep='\t', comment='#')

      df = self.expand_curie(df, sssom_metadata)

      df = self.add_id(df)

      df = self.add_mapping_date(df, sssom_metadata)

      df = self.add_datasource(df)

      df = self.mapping_scope(df)

      df.to_csv(mapping_path, sep='\t', index=False)

      with open(metadata_path, 'w') as file:
        yaml.dump(sssom_metadata, file)
      
    def expand_curie(self, df, sssom_metadata):
      if 'curie_map' in sssom_metadata:
        df['subject_uri'] = None
        df['object_uri'] = None
        curie_map = sssom_metadata["curie_map"]
        for i, row in df.iterrows():
          sub = row['subject_id'].split(":")
          obj = row['object_id'].split(":")
        
          if curie_map.get(sub[0]):
            df.loc[i,'subject_uri'] = sssom_metadata["curie_map"][sub[0]] + sub[1]
          if curie_map.get(obj[0]):
            df.loc[i, 'object_uri'] = sssom_metadata["curie_map"][obj[0]] + obj[1]
        
        return df
      else:
        return df

    def _read_metadata_from_table(self, path):
      response = urlopen(path)
      yamlstr = ""
      for lin in response:
          line = lin.decode("utf-8")
          if line.startswith("#"):
              yamlstr += re.sub("^#", "", line)
          else:
              break

      if yamlstr:
        meta = yaml.safe_load(yamlstr)
        return meta
      return {}

    def add_id(self, df):
      df['subject_identifier'] = ""
      df['object_identifier'] = ""

      for i, row in df.iterrows():
        df.loc[i, 'subject_identifier'] = self.get_id_from_curie(row['subject_id'])
        df.loc[i, 'object_identifier'] = self.get_id_from_curie(row['object_id'])
      return df
    
    def get_id_from_curie(self, curie):
      return curie.split(':')[1]

    def add_mapping_date(self, df, sssom_metadata):
      if 'mapping_date' in sssom_metadata:
        df['mapping_date'] = sssom_metadata['mapping_date']
      else:
        df['mapping_date'] = date(2000, 1, 1).isoformat()
      return df
      
    def add_datasource(self, df):
      df["datasource"] = None
      for i, row in df.iterrows():
        datasource = {
          "prefix": None,
          "name": None,
          "source": None,
          "idorgNamespace": None,
          "alternatePrefix": None,
          "licence": None,
          "versionInfo": None,
          "preferredPrefix": None
        }
        datasource["prefix"] = row["subject_source"]
        datasource["name"] = row["subject_source"]
        datasource["source"] = "ONTOLOGY"
        datasource["alternatePrefix"] = [row["subject_source"]]
        datasource["preferredPrefix"] = row["subject_source"]

        df["datasource"].iloc[i] = json.dumps(datasource)

      return df

    def mapping_scope(self, df):
      SCOPE = {
        "owl:equivalentClass": "EXACT"
      }
      df["scope"] = None
      
      for key, value in SCOPE.items():
        df.loc[(df["predicate_id"] == key), 'scope'] = SCOPE[key]
      return df

if __name__ == '__main__':
    Neo4jOxOLoader()

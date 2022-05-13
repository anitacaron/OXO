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
import yaml

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

        self.session.run("CREATE CONSTRAINT IF NOT EXISTS ON (i:Term) ASSERT i.curie IS UNIQUE")
        self.session.run("CREATE CONSTRAINT IF NOT EXISTS ON (i:Datasource) ASSERT i.prefix IS UNIQUE")

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
            SET t1.label = CASE trim(row.subject_label) WHEN "" THEN null ELSE row.subject_label END
            SET t1.category = CASE trim(row.subject_category) WHEN "" THEN null ELSE row.subject_category END
            WITH row
            MERGE (t2:Term { curie: row.object_id})
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
            MERGE (subject)-[m:MAPPING { predicate: row.predicate_id, matchType: row.match_type, mappingTool: row.mapping_tool, confidence: row.confidence, matchCategory: row.match_category}]->(object)
            SET m.matchString = CASE trim(row.match_string) WHEN "" THEN null ELSE row.match_string END
          """

        result = self.session.run(load_mappings_cypher)
        print(result.consume())

    def load_datasources(self, datasources):
        print("Loading datasources from " + datasources + " ...")
        load_datasources_cypher = """
            LOAD CSV WITH HEADERS FROM 'file:///"""+datasources+"""' AS row
            FIELDTERMINATOR '\t'
            WITH row
            MERGE (d1:Datasource {prefix : row.subject_source})
            MERGE (d2:Datasource {prefix : row.object_source})
        """
        # WITH d, line
        #SET d.preferredPrefix = line.prefix, d.name = line.title, d.description = line.description, d.versionInfo = line.versionInfo, d.idorgNamespace = line.idorgNamespace, d.licence = line.licence, d.sourceType = line.sourceType, d.alternatePrefix = split(line.alternatePrefixes,",")
        self.session.run(load_datasources_cypher)

    def preprocess(self, mapping_path, metadata_path):
      sssom_metadata = self._read_metadata_from_table(mapping_path)
      
      df = pd.read_csv(mapping_path, sep='\t', comment='#')

      df = self.expand_curie(df, sssom_metadata)

      df.to_csv(mapping_path, sep='\t', index=False)

      with open(metadata_path, 'w') as file:
        yaml.dump(sssom_metadata, file)
      
    def expand_curie(self, df, sssom_metadata):
      if 'curie_map' in sssom_metadata:
        df['subject_uri'] = None
        df['object_uri'] = None
        for _, row in df.iterrows():
          subject = row['subject_id'].split(":")
          object_ = row['object_id'].split(":")
          for k, v in sssom_metadata['curie_map'].items():
            if sssom_metadata["curie_map"][k] == subject[0]:
              df['subject_uri'] = sssom_metadata["curie_map"][subject[0]] + subject[1]
              df['object_uri'] = sssom_metadata["curie_map"][object_[0]] + object_[1]
        
        return df
      else:
        return df

    def _read_metadata_from_table(self, path):
      with open(path) as file:
          yamlstr = ""
          for line in file:
              if line.startswith("#"):
                  yamlstr += re.sub("^#", "", line)
              else:
                  break

      if yamlstr:
        meta = yaml.safe_load(yamlstr)
        return meta
      return {}
      

if __name__ == '__main__':
    Neo4jOxOLoader()

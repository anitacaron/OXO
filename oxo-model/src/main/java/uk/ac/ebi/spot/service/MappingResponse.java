package uk.ac.ebi.spot.service;

import java.util.Collection;

import uk.ac.ebi.spot.model.Scope;

/**
 * @author Simon Jupp
 * @since 30/08/2016
 * Samples, Phenotypes and Ontologies Team, EMBL-EBI
 */
public class MappingResponse {

    private String curie;
    private String label;
    private Collection<String> sourcePrefixes;
    private String targetPrefix;
    private int distance;
    private Scope scope;

    public MappingResponse() {
    }

    public MappingResponse(String curie, String label, Collection<String> sourcePrefixes, String targetPrefix, int distance, Scope scope) {
        this.curie = curie;
        this.label = label;
        this.sourcePrefixes = sourcePrefixes;
        this.targetPrefix = targetPrefix;
        this.distance = distance;
        this.scope = scope;
    }

    public String getCurie() {
        return curie;
    }

    public void setCurie(String curie) {
        this.curie = curie;
    }

    public String getLabel() {
        return label;
    }

    public void setLabel(String label) {
        this.label = label;
    }

    public Collection<String> getSourcePrefixes() {
        return sourcePrefixes;
    }

    public void setSourcePrefixes(Collection<String> sourcePrefixes) {
        this.sourcePrefixes = sourcePrefixes;
    }

    public String getTargetPrefix() {
        return targetPrefix;
    }

    public void setTargetPrefix(String targetPrefix) {
        this.targetPrefix = targetPrefix;
    }

    public int getDistance() {
        return distance;
    }

    public void setDistance(int distance) {
        this.distance = distance;
    }
    
    public Scope getScope() {
        return this.scope;
    }
  
    public void setScope(Scope scope) {
        this.scope = scope;
    }
}


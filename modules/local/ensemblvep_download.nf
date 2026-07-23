process ENSEMBLVEP_DOWNLOAD {
    tag "${species}.${genome}.${cache_version}"
    label 'process_medium'

    conda 'bioconda::ensembl-vep=111.0'
    container 'biocontainers/ensembl-vep:111.0--pl5321h2a3209d_0'

    input:
    val genome         // assembly, e.g. 'GRCh38'
    val species        // e.g. 'homo_sapiens'
    val cache_version  // e.g. '111'

    output:
    path 'vep_cache',    emit: cache
    path 'versions.yml', emit: versions

    // Download an Ensembl VEP cache (multi-GB for human). The real-genome,
    // full-scale annotation alternative to SnpEff. Run on a real host.
    script:
    """
    mkdir -p vep_cache
    vep_install --AUTO c --CACHEDIR vep_cache \\
        --SPECIES ${species} --ASSEMBLY ${genome} \\
        --CACHE_VERSION ${cache_version} --NO_UPDATE --NO_HTSLIB

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        ensembl-vep: \$( vep --help 2>&1 | sed -n 's/.*ensembl-vep : //p' | head -1 )
    END_VERSIONS
    """

    stub:
    """
    mkdir -p vep_cache/${species}/${cache_version}_${genome}
    echo '"${task.process}": {ensembl-vep: stub}' > versions.yml
    """
}

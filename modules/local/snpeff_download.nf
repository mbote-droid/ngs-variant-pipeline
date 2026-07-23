process SNPEFF_DOWNLOAD {
    tag "$db"
    label 'process_medium'

    conda 'bioconda::snpeff=5.2'
    container 'biocontainers/snpeff:5.2--hdfd78af_0'

    input:
    val db      // prebuilt SnpEff database name, e.g. 'GRCh38.105'

    output:
    tuple path('data'), path('snpEff.config'), emit: db
    path 'versions.yml',                       emit: versions

    // Download a prebuilt SnpEff database (the real-genome alternative to the
    // offline build in SNPEFF_BUILD). Emits the same [data, config] tuple, so
    // SNPEFF_ANN is unchanged downstream. Needs network + disk (multi-GB for a
    // full human DB) - run on a real host, not in the offline test profile.
    script:
    """
    mkdir -p data
    printf 'data.dir = ./data/\\n' > snpEff.config
    snpEff download -dataDir \$PWD/data -c snpEff.config -v ${db}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        snpeff: \$( snpEff -version 2>&1 | sed 's/SnpEff\\s*//' | head -1 )
    END_VERSIONS
    """

    stub:
    """
    mkdir -p data/${db}
    touch data/${db}/snpEffectPredictor.bin
    printf 'data.dir = ./data/\\n' > snpEff.config
    echo '"${task.process}": {snpeff: stub}' > versions.yml
    """
}

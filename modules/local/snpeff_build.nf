process SNPEFF_BUILD {
    tag "$db"
    label 'process_medium'

    conda 'bioconda::snpeff=5.2'
    container 'biocontainers/snpeff:5.2--hdfd78af_0'

    input:
    path fasta
    path gff
    val  db      // database name (params.snpeff_db)

    output:
    tuple path('data'), path('snpEff.config'), emit: db
    path 'versions.yml',                       emit: versions

    script:
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    // Build a SnpEff database from local files only - no download, fully offline.
    // -noCheck* tolerates a synthetic gene model that need not translate cleanly.
    """
    mkdir -p data/${db}
    cp ${fasta} data/${db}/sequences.fa
    cp ${gff}   data/${db}/genes.gff
    printf '%s.genome : %s\\n' "${db}" "${db}" > snpEff.config

    snpEff build -Xmx${avail_mem}g \\
        -gff3 -noCheckCds -noCheckProtein \\
        -dataDir \$PWD/data -c snpEff.config -v ${db}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        snpeff: \$( snpEff -version 2>&1 | sed 's/SnpEff\\s*//' | head -1 )
    END_VERSIONS
    """

    stub:
    """
    mkdir -p data/${db}
    touch data/${db}/snpEffectPredictor.bin
    printf '%s.genome : %s\\n' "${db}" "${db}" > snpEff.config
    echo '"${task.process}": {snpeff: stub}' > versions.yml
    """
}

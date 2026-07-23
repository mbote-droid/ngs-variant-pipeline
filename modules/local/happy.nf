process HAPPY {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::hap.py=0.3.15'
    container 'biocontainers/hap.py:0.3.15--py27hb763c3d_1'

    input:
    tuple val(meta), path(vcf), path(tbi)
    path truth       // truth/gold-standard VCF
    path bed         // high-confidence regions BED, or [] if none
    path fasta       // reference FASTA
    path fai         // reference .fai

    output:
    tuple val(meta), path('*.summary.csv'), emit: summary
    path 'versions.yml',                    emit: versions

    // GA4GH-standard benchmarking (hap.py). Handles complex variant
    // representation the built-in matcher does not. Real gold standard (GIAB).
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    conf_arg=""
    if [ -s "${bed}" ]; then conf_arg="-f ${bed}"; fi

    hap.py ${truth} ${vcf} -r ${fasta} -o ${prefix} \$conf_arg \\
        --threads ${task.cpus}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        hap.py: \$( hap.py --version 2>&1 | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    printf 'Type,Filter,TRUTH.TP,TRUTH.FN,QUERY.FP\\nSNP,PASS,0,0,0\\nINDEL,PASS,0,0,0\\n' \\
        > ${prefix}.summary.csv
    echo '"${task.process}": {hap.py: stub}' > versions.yml
    """
}

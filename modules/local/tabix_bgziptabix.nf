process TABIX_BGZIPTABIX {
    tag "$vcf"
    label 'process_single'

    conda 'bioconda::tabix=1.11'
    container 'biocontainers/tabix:1.11--hdfd78af_0'

    input:
    path vcf

    output:
    tuple path('*.gz'), path('*.tbi'), emit: gz_tbi
    path 'versions.yml',               emit: versions

    script:
    """
    bgzip -c ${vcf} > ${vcf}.gz
    tabix -p vcf ${vcf}.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tabix: \$( tabix --version | head -1 | sed 's/tabix (htslib) //' )
    END_VERSIONS
    """

    stub:
    """
    touch ${vcf}.gz ${vcf}.gz.tbi
    echo '"${task.process}": {tabix: stub}' > versions.yml
    """
}

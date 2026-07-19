process BCFTOOLS_STATS {
    tag "$meta.id"
    label 'process_single'

    // gsl is pinned explicitly: the bcftools 1.19 build links libgsl.so.25
    // (gsl 2.7); without the pin the solver can pull an incompatible gsl.
    conda 'bioconda::bcftools=1.19 conda-forge::gsl=2.7'
    container 'biocontainers/bcftools:1.19--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path('*.bcftools_stats.txt'), emit: stats
    path 'versions.yml',                           emit: versions

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    bcftools stats ${vcf} > ${prefix}.bcftools_stats.txt

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$( bcftools --version | head -1 | sed 's/bcftools //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.bcftools_stats.txt
    echo '"${task.process}": {bcftools: stub}' > versions.yml
    """
}

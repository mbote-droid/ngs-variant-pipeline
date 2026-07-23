process ENSEMBLVEP_VEP {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::ensembl-vep=111.0'
    container 'biocontainers/ensembl-vep:111.0--pl5321h2a3209d_0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    path fasta
    path cache
    val  genome
    val  species
    val  cache_version

    output:
    tuple val(meta), path('*.vep.vcf.gz'), path('*.vep.vcf.gz.tbi'), emit: vcf
    tuple val(meta), path('*.vep.summary.html'),                     emit: report
    path 'versions.yml',                                             emit: versions

    // Ensembl VEP annotation (the full-scale alternative to SnpEff). Emits a
    // CSQ-annotated, bgzipped+indexed VCF; prioritize_variants.py reads either
    // SnpEff ANN or VEP CSQ. Uses the vep container's bundled htslib (bgzip/tabix).
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    vep --offline --cache --dir_cache ${cache} \\
        --species ${species} --assembly ${genome} --cache_version ${cache_version} \\
        --fasta ${fasta} --vcf --compress_output bgzip --force_overwrite \\
        --stats_file ${prefix}.vep.summary.html \\
        --input_file ${vcf} --output_file ${prefix}.vep.vcf.gz
    tabix -p vcf ${prefix}.vep.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        ensembl-vep: \$( vep --help 2>&1 | sed -n 's/.*ensembl-vep : //p' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.vep.vcf.gz
    touch ${prefix}.vep.vcf.gz.tbi ${prefix}.vep.summary.html
    echo '"${task.process}": {ensembl-vep: stub}' > versions.yml
    """
}

process BENCHMARK_VCF {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(vcf), path(tbi)
    path truth       // truth/gold-standard VCF
    path bed         // high-confidence regions BED, or [] if none

    output:
    tuple val(meta), path('*.benchmark.json'), emit: json
    tuple val(meta), path('*.benchmark.tsv'),  emit: tsv
    path 'versions.yml',                       emit: versions

    // Lightweight stdlib concordance benchmark (benchmark_vcf.py on PATH via bin/).
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    bed_arg=""
    if [ -s "${bed}" ]; then bed_arg="--bed ${bed}"; fi

    benchmark_vcf.py ${vcf} ${truth} \$bed_arg \\
        --sample ${meta.id} \\
        --json ${prefix}.benchmark.json --tsv ${prefix}.benchmark.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // runs the real (stdlib) benchmark so downstream files are well-formed
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    bed_arg=""
    if [ -s "${bed}" ]; then bed_arg="--bed ${bed}"; fi
    benchmark_vcf.py ${vcf} ${truth} \$bed_arg --sample ${meta.id} \\
        --json ${prefix}.benchmark.json --tsv ${prefix}.benchmark.tsv
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}

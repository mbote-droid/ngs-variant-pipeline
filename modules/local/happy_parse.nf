process HAPPY_PARSE {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(summary)

    output:
    tuple val(meta), path('*.benchmark.json'), emit: json
    tuple val(meta), path('*.benchmark.tsv'),  emit: tsv
    path 'versions.yml',                       emit: versions

    // Fold hap.py's summary.csv into the same metrics shape as BENCHMARK_VCF
    // (parse_happy.py on PATH via bin/).
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    parse_happy.py ${summary} --sample ${meta.id} \\
        --json ${prefix}.benchmark.json --tsv ${prefix}.benchmark.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    parse_happy.py ${summary} --sample ${meta.id} \\
        --json ${prefix}.benchmark.json --tsv ${prefix}.benchmark.tsv
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}

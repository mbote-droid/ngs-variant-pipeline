process PRIORITIZE_VARIANTS {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path('*.prioritized.tsv'),  emit: tsv
    tuple val(meta), path('*.prioritized.json'), emit: json
    path 'versions.yml',                         emit: versions

    script:  // prioritize_variants.py is on PATH via bin/
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    prioritize_variants.py ${vcf} \\
        --sample ${meta.id} \\
        --tsv ${prefix}.prioritized.tsv \\
        --json ${prefix}.prioritized.json

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // runs the real (stdlib-only) script so the JSON is well-formed downstream
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    prioritize_variants.py ${vcf} --sample ${meta.id} \\
        --tsv ${prefix}.prioritized.tsv --json ${prefix}.prioritized.json
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}

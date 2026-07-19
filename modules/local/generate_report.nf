process GENERATE_REPORT {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(prioritized_json)
    val  enable_llm

    output:
    tuple val(meta), path('*.report.html'), emit: html
    tuple val(meta), path('*.report.json'), emit: report_json
    tuple val(meta), path('*.fhir.json'),   emit: fhir
    path 'versions.yml',                     emit: versions

    script:  // generate_report.py is on PATH via bin/
    def prefix  = task.ext.prefix ?: "${meta.id}"
    def llm_flag = enable_llm ? '--llm' : ''
    """
    generate_report.py ${prioritized_json} --prefix ${prefix} ${llm_flag}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // runs the real (stdlib-only) generator on the upstream JSON
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    generate_report.py ${prioritized_json} --prefix ${prefix}
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}

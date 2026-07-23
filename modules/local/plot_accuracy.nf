process PLOT_ACCURACY {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(benchmark_json)

    output:
    tuple val(meta), path('*.svg'), emit: plots
    path 'versions.yml',            emit: versions

    // Render PR-curve / F1-by-type / genotype-confusion SVGs from the benchmark
    // JSON (plot_accuracy.py on PATH via bin/). Stdlib-only; no plotting library.
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    plot_accuracy.py ${benchmark_json} --outdir . --prefix ${prefix}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // runs the real (stdlib) renderer so the SVGs are well-formed
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    plot_accuracy.py ${benchmark_json} --outdir . --prefix ${prefix}
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}

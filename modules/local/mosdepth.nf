process MOSDEPTH {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::mosdepth=0.3.8'
    container 'biocontainers/mosdepth:0.3.8--hd299d5a_0'

    input:
    tuple val(meta), path(bam), path(bai)

    output:
    tuple val(meta), path('*.mosdepth.summary.txt'),      emit: summary
    tuple val(meta), path('*.mosdepth.global.dist.txt'),  emit: global_dist
    path 'versions.yml',                                  emit: versions

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    mosdepth --no-per-base --fast-mode -t ${task.cpus} ${prefix} ${bam}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        mosdepth: \$( mosdepth --version | sed 's/mosdepth //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.mosdepth.summary.txt ${prefix}.mosdepth.global.dist.txt
    echo '"${task.process}": {mosdepth: stub}' > versions.yml
    """
}

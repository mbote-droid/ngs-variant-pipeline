process CAT_FASTQ {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::coreutils=9.5'
    container 'ubuntu:22.04'

    input:
    tuple val(meta), path(reads, stageAs: "input*/*")

    output:
    tuple val(meta), path("*.merged.fastq.gz"), emit: reads
    path 'versions.yml',                        emit: versions

    // Merge a sample's lanes into one FASTQ (per read end). Concatenated gzip
    // streams are themselves valid gzip, so a plain `cat` is correct for
    // bgzipped/gzipped FASTQs. Only runs for samples with >1 lane.
    script:
    def prefix   = task.ext.prefix ?: "${meta.id}"
    def readList = (reads instanceof List ? reads : [reads]).collect { it.toString() }
    if (meta.single_end) {
        """
        cat ${readList.join(' ')} > ${prefix}.merged.fastq.gz

        cat <<-END_VERSIONS > versions.yml
        "${task.process}":
            cat: \$( cat --version | head -1 | sed 's/^.*coreutils) //' )
        END_VERSIONS
        """
    } else {
        def r1 = []
        def r2 = []
        readList.eachWithIndex { v, i -> (i % 2 == 0 ? r1 : r2) << v }
        """
        cat ${r1.join(' ')} > ${prefix}_1.merged.fastq.gz
        cat ${r2.join(' ')} > ${prefix}_2.merged.fastq.gz

        cat <<-END_VERSIONS > versions.yml
        "${task.process}":
            cat: \$( cat --version | head -1 | sed 's/^.*coreutils) //' )
        END_VERSIONS
        """
    }

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    def outs   = meta.single_end ? "${prefix}.merged.fastq.gz"
                                 : "${prefix}_1.merged.fastq.gz ${prefix}_2.merged.fastq.gz"
    """
    touch ${outs}
    echo '"${task.process}": {cat: stub}' > versions.yml
    """
}

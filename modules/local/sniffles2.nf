process SNIFFLES2 {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::sniffles=2.3.3'
    container 'biocontainers/sniffles:2.3.3--pyhdfd78af_0'

    input:
    tuple val(meta), path(bam), path(bai)
    path fasta

    output:
    tuple val(meta), path('*.sniffles.vcf'), emit: sv_vcf
    path 'versions.yml',                     emit: versions

    // Long-read structural-variant calling (M9). Sniffles2 detects insertions,
    // deletions, duplications, inversions and translocations that short reads
    // miss. Emitted as a separate SV VCF (SVs use different annotation than the
    // small-variant report path).
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    sniffles \\
        --input ${bam} \\
        --reference ${fasta} \\
        --threads ${task.cpus} \\
        --vcf ${prefix}.sniffles.vcf

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sniffles: \$( sniffles --version 2>&1 | sed 's/^.*Version //' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    printf '##fileformat=VCFv4.2\\n#CHROM\\tPOS\\tID\\tREF\\tALT\\tQUAL\\tFILTER\\tINFO\\tFORMAT\\t${meta.id}\\n' \\
        > ${prefix}.sniffles.vcf
    echo '"${task.process}": {sniffles: stub}' > versions.yml
    """
}

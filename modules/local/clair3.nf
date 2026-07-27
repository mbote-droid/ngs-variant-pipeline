process CLAIR3 {
    tag "$meta.id"
    label 'process_high'

    conda 'bioconda::clair3=1.0.10'
    container 'biocontainers/clair3:1.0.10--py39hb9dc472_0'

    input:
    tuple val(meta), path(bam), path(bai)
    path fasta
    path fai
    val  platform          // 'ont' or 'hifi' (Clair3 --platform)
    path model             // Clair3 model directory (may be [] for stub)

    output:
    tuple val(meta), path('*.clair3.vcf.gz'), path('*.clair3.vcf.gz.tbi'), emit: vcf
    path 'versions.yml',                                                   emit: versions

    // Long-read small-variant calling (M9). Clair3 is a deep-learning caller;
    // it needs a platform-matched model (--clair3_model). merge_output.vcf.gz is
    // renamed to the pipeline's per-sample convention for annotation/report.
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    run_clair3.sh \\
        --bam_fn=${bam} \\
        --ref_fn=${fasta} \\
        --threads=${task.cpus} \\
        --platform=${platform} \\
        --model_path=${model} \\
        --output=clair3_out

    cp clair3_out/merge_output.vcf.gz     ${prefix}.clair3.vcf.gz
    cp clair3_out/merge_output.vcf.gz.tbi ${prefix}.clair3.vcf.gz.tbi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        clair3: \$( run_clair3.sh --version 2>&1 | sed 's/^.*Clair3 //' | head -1 )
    END_VERSIONS
    """

    stub:  // produce a well-formed empty bgzipped VCF so downstream stages parse
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    printf '##fileformat=VCFv4.2\\n#CHROM\\tPOS\\tID\\tREF\\tALT\\tQUAL\\tFILTER\\tINFO\\tFORMAT\\t${meta.id}\\n' \\
        | gzip > ${prefix}.clair3.vcf.gz
    touch ${prefix}.clair3.vcf.gz.tbi
    echo '"${task.process}": {clair3: stub}' > versions.yml
    """
}

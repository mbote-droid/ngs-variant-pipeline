process EVIDENCE_ANNOTATE {
    tag "$meta.id"
    label 'process_single'

    conda 'bioconda::bcftools=1.19 conda-forge::gsl=2.7'
    container 'biocontainers/bcftools:1.19--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    path clinvar   // ClinVar sites VCF (bgzipped) or [] if absent
    path gnomad    // gnomAD sites VCF  (bgzipped) or []
    path dbsnp     // dbSNP VCF         (bgzipped) or []

    output:
    tuple val(meta), path('*.evidence.vcf.gz'), path('*.evidence.vcf.gz.tbi'), emit: vcf
    path 'versions.yml',                                                        emit: versions

    // Layer clinical + population evidence onto the functionally-annotated VCF
    // (H3). Each track is optional; only supplied ones are applied, in sequence,
    // with bcftools annotate. Field names (gnomAD_AF, CLNSIG, dbSNP ID) are the
    // ones prioritize_variants.py reads. Provide bgzipped tracks; they are
    // (re)indexed here in case a .tbi is missing.
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    cur=${vcf}

    if [ -s "${clinvar}" ]; then
        bcftools index -f -t ${clinvar}
        bcftools annotate -a ${clinvar} \\
            -c INFO/CLNSIG,INFO/CLNSIGCONF,INFO/CLNREVSTAT,INFO/CLNDN \\
            -Oz -o step.clinvar.vcf.gz "\$cur"
        bcftools index -f -t step.clinvar.vcf.gz
        cur=step.clinvar.vcf.gz
    fi

    if [ -s "${gnomad}" ]; then
        bcftools index -f -t ${gnomad}
        bcftools annotate -a ${gnomad} \\
            -c INFO/gnomAD_AF:=INFO/AF \\
            -Oz -o step.gnomad.vcf.gz "\$cur"
        bcftools index -f -t step.gnomad.vcf.gz
        cur=step.gnomad.vcf.gz
    fi

    if [ -s "${dbsnp}" ]; then
        bcftools index -f -t ${dbsnp}
        bcftools annotate -a ${dbsnp} -c ID \\
            -Oz -o step.dbsnp.vcf.gz "\$cur"
        bcftools index -f -t step.dbsnp.vcf.gz
        cur=step.dbsnp.vcf.gz
    fi

    cp "\$cur" ${prefix}.evidence.vcf.gz
    bcftools index -f -t ${prefix}.evidence.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$( bcftools --version | head -1 | sed 's/bcftools //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.evidence.vcf.gz
    touch ${prefix}.evidence.vcf.gz.tbi
    echo '"${task.process}": {bcftools: stub}' > versions.yml
    """
}

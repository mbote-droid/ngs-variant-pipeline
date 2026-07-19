//
// Germline short-variant calling: GATK HaplotypeCaller (GVCF) -> GenotypeGVCFs
// -> hard-filter labelling, plus bcftools stats for MultiQC. Emits a filtered
// VCF for annotation (M4).
//

include { GATK4_HAPLOTYPECALLER  } from '../../modules/local/gatk4_haplotypecaller'
include { GATK4_GENOTYPEGVCFS    } from '../../modules/local/gatk4_genotypegvcfs'
include { GATK4_VARIANTFILTRATION } from '../../modules/local/gatk4_variantfiltration'
include { BCFTOOLS_STATS         } from '../../modules/local/bcftools_stats'

workflow CALL_VARIANTS {
    take:
    bam    // channel: [ meta, bam, bai ]
    fasta  // value:   path(fasta)
    fai    // value:   path(fai)
    dict   // value:   path(dict)

    main:
    ch_versions = Channel.empty()

    GATK4_HAPLOTYPECALLER ( bam, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_HAPLOTYPECALLER.out.versions.first() )

    GATK4_GENOTYPEGVCFS ( GATK4_HAPLOTYPECALLER.out.gvcf, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_GENOTYPEGVCFS.out.versions.first() )

    GATK4_VARIANTFILTRATION ( GATK4_GENOTYPEGVCFS.out.vcf, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_VARIANTFILTRATION.out.versions.first() )

    BCFTOOLS_STATS ( GATK4_VARIANTFILTRATION.out.vcf )
    ch_versions = ch_versions.mix( BCFTOOLS_STATS.out.versions.first() )

    emit:
    vcf      = GATK4_VARIANTFILTRATION.out.vcf   // [ meta, vcf, tbi ]
    stats    = BCFTOOLS_STATS.out.stats
    versions = ch_versions
}

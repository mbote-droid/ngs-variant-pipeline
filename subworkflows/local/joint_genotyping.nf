//
// H5: cohort joint genotyping (GATK best practice).
//
// Per-sample GATK4 HaplotypeCaller (GVCF) -> CombineGVCFs across all samples ->
// GenotypeGVCFs once on the cohort -> hard-filter labelling -> bcftools stats.
// Emits a single multi-sample (cohort) VCF. Opt-in via --joint; the per-sample
// path (subworkflows/local/call_variants.nf) is unchanged.
//

include { GATK4_HAPLOTYPECALLER   } from '../../modules/local/gatk4_haplotypecaller'
include { GATK4_COMBINEGVCFS       } from '../../modules/local/gatk4_combinegvcfs'
include { GATK4_GENOTYPEGVCFS      } from '../../modules/local/gatk4_genotypegvcfs'
include { GATK4_VARIANTFILTRATION  } from '../../modules/local/gatk4_variantfiltration'
include { BCFTOOLS_STATS           } from '../../modules/local/bcftools_stats'

workflow JOINT_GENOTYPING {
    take:
    bam        // channel: [ meta, bam, bai ] per sample
    fasta      // value:   path(fasta)
    fai        // value:   path(fai)
    dict       // value:   path(dict)
    cohort_id  // val:     cohort identifier

    main:
    ch_versions = Channel.empty()

    GATK4_HAPLOTYPECALLER ( bam, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_HAPLOTYPECALLER.out.versions.first() )

    // Gather every sample's GVCF into a single cohort group.
    ch_cohort_gvcfs = GATK4_HAPLOTYPECALLER.out.gvcf
        .map { meta, gvcf, tbi -> [ gvcf, tbi ] }
        .toList()
        .map { pairs ->
            [ [ id: cohort_id ], pairs.collect { it[0] }, pairs.collect { it[1] } ]
        }

    GATK4_COMBINEGVCFS ( ch_cohort_gvcfs, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_COMBINEGVCFS.out.versions )

    GATK4_GENOTYPEGVCFS ( GATK4_COMBINEGVCFS.out.gvcf, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_GENOTYPEGVCFS.out.versions )

    GATK4_VARIANTFILTRATION ( GATK4_GENOTYPEGVCFS.out.vcf, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_VARIANTFILTRATION.out.versions )

    BCFTOOLS_STATS ( GATK4_VARIANTFILTRATION.out.vcf )
    ch_versions = ch_versions.mix( BCFTOOLS_STATS.out.versions )

    emit:
    vcf      = GATK4_VARIANTFILTRATION.out.vcf   // [ meta(cohort), vcf, tbi ]
    stats    = BCFTOOLS_STATS.out.stats
    versions = ch_versions
}

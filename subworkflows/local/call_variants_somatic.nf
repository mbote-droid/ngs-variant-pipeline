//
// M7: somatic short-variant calling (tumor/normal).
//
// Pairs each tumor BAM with its matched normal by `meta.patient`, then runs
// GATK4 Mutect2 -> LearnReadOrientationModel -> FilterMutectCalls. Optional
// panel-of-normals and germline-resource are passed through when provided.
// Emits a filtered somatic VCF for annotation/report (reuses the germline
// downstream unchanged).
//

include { GATK4_MUTECT2                 } from '../../modules/local/gatk4_mutect2'
include { GATK4_LEARNREADORIENTATIONMODEL } from '../../modules/local/gatk4_learnreadorientationmodel'
include { GATK4_FILTERMUTECTCALLS       } from '../../modules/local/gatk4_filtermutectcalls'

workflow CALL_VARIANTS_SOMATIC {
    take:
    bam           // channel: [ meta, bam, bai ]  (meta has .status and .patient)
    fasta         // value:   path(fasta)
    fai           // value:   path(fai)
    dict          // value:   path(dict)
    pon           // value:   path(pon)      or []
    pon_tbi       // value:   path(pon.tbi)  or []
    germline      // value:   path(germline) or []
    germline_tbi  // value:   path(germline.tbi) or []

    main:
    ch_versions = Channel.empty()

    // Split into tumor (status 1) and normal (status 0), key by patient, pair.
    ch_split = bam.branch { meta, b, i ->
        tumor:  meta.status == 1
        normal: meta.status == 0
    }
    ch_tumor  = ch_split.tumor.map  { meta, b, i -> [ meta.patient, meta, b, i ] }
    ch_normal = ch_split.normal.map { meta, b, i -> [ meta.patient, meta, b, i ] }

    ch_pairs = ch_tumor
        .combine( ch_normal, by: 0 )
        .map { patient, tmeta, tbam, tbai, nmeta, nbam, nbai ->
            def meta = [ id: tmeta.id, patient: patient,
                         tumor_id: tmeta.id, normal_id: nmeta.id ]
            [ meta, tbam, tbai, nbam, nbai ]
        }

    GATK4_MUTECT2 ( ch_pairs, fasta, fai, dict, pon, pon_tbi, germline, germline_tbi )
    ch_versions = ch_versions.mix( GATK4_MUTECT2.out.versions.first() )

    GATK4_LEARNREADORIENTATIONMODEL ( GATK4_MUTECT2.out.f1r2 )
    ch_versions = ch_versions.mix( GATK4_LEARNREADORIENTATIONMODEL.out.versions.first() )

    ch_filter_in = GATK4_MUTECT2.out.vcf
        .join( GATK4_MUTECT2.out.stats, by: 0 )
        .join( GATK4_LEARNREADORIENTATIONMODEL.out.model, by: 0 )
        .map { meta, vcf, tbi, stats, model -> [ meta, vcf, tbi, stats, model ] }

    GATK4_FILTERMUTECTCALLS ( ch_filter_in, fasta, fai, dict )
    ch_versions = ch_versions.mix( GATK4_FILTERMUTECTCALLS.out.versions.first() )

    emit:
    vcf      = GATK4_FILTERMUTECTCALLS.out.vcf   // [ meta, vcf, tbi ]
    versions = ch_versions
}

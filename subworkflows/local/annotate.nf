//
// Variant annotation with SnpEff. The database is built from local reference +
// GFF3 files, so this runs fully offline (no multi-GB cache download). Emits an
// annotated VCF for prioritization (M5) and a CSV report for MultiQC.
//

include { SNPEFF_BUILD } from '../../modules/local/snpeff_build'
include { SNPEFF_ANN   } from '../../modules/local/snpeff_ann'

workflow ANNOTATE {
    take:
    vcf    // channel: [ meta, vcf, tbi ]
    fasta  // value:   path(fasta)
    gff    // value:   path(gff)
    db     // val:     database name

    main:
    ch_versions = Channel.empty()

    SNPEFF_BUILD ( fasta, gff, db )
    ch_versions = ch_versions.mix( SNPEFF_BUILD.out.versions )

    SNPEFF_ANN ( vcf, SNPEFF_BUILD.out.db.first(), db )
    ch_versions = ch_versions.mix( SNPEFF_ANN.out.versions.first() )

    emit:
    vcf      = SNPEFF_ANN.out.vcf      // [ meta, vcf, tbi ]
    report   = SNPEFF_ANN.out.report   // [ meta, csv ]
    versions = ch_versions
}

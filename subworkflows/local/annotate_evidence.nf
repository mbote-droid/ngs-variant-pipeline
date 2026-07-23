//
// H3: optional clinical + population evidence overlay.
//
// When any of --clinvar / --gnomad / --dbsnp is supplied, layer those tracks
// onto the functionally-annotated VCF (ClinVar significance, gnomAD population
// AF, dbSNP rsIDs). When none are supplied this is a pure pass-through, so the
// default/offline DAG is byte-for-byte unchanged and the process never enters
// the graph.
//

include { EVIDENCE_ANNOTATE } from '../../modules/local/evidence_annotate'

workflow ANNOTATE_EVIDENCE {
    take:
    vcf    // channel: [ meta, vcf, tbi ]

    main:
    ch_versions = Channel.empty()

    def has_evidence = params.clinvar || params.gnomad || params.dbsnp

    if ( has_evidence ) {
        ch_clinvar = params.clinvar ? Channel.fromPath(params.clinvar, checkIfExists: true).first() : Channel.value([])
        ch_gnomad  = params.gnomad  ? Channel.fromPath(params.gnomad,  checkIfExists: true).first() : Channel.value([])
        ch_dbsnp   = params.dbsnp   ? Channel.fromPath(params.dbsnp,   checkIfExists: true).first() : Channel.value([])

        EVIDENCE_ANNOTATE ( vcf, ch_clinvar, ch_gnomad, ch_dbsnp )
        ch_out      = EVIDENCE_ANNOTATE.out.vcf
        ch_versions = ch_versions.mix( EVIDENCE_ANNOTATE.out.versions.first() )
    }
    else {
        ch_out = vcf
    }

    emit:
    vcf      = ch_out
    versions = ch_versions
}

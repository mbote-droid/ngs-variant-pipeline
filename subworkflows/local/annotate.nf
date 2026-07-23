//
// Variant annotation. Default (offline, synthetic-safe): build a SnpEff database
// from local reference + GFF3 - no multi-GB download. Real-genome alternatives
// (H2): download a prebuilt SnpEff cache, or annotate with Ensembl VEP.
// Optionally layer clinical/population evidence (H3: ClinVar/gnomAD/dbSNP).
// Emits an annotated VCF for prioritization (M5) and a report for MultiQC.
//

include { SNPEFF_BUILD        } from '../../modules/local/snpeff_build'
include { SNPEFF_DOWNLOAD     } from '../../modules/local/snpeff_download'
include { SNPEFF_ANN          } from '../../modules/local/snpeff_ann'
include { ENSEMBLVEP_DOWNLOAD } from '../../modules/local/ensemblvep_download'
include { ENSEMBLVEP_VEP      } from '../../modules/local/ensemblvep_vep'
include { ANNOTATE_EVIDENCE   } from './annotate_evidence'

workflow ANNOTATE {
    take:
    vcf    // channel: [ meta, vcf, tbi ]
    fasta  // value:   path(fasta)
    gff    // value:   path(gff) or []
    db     // val:     database name

    main:
    ch_versions = Channel.empty()

    if ( params.annotator == 'vep' ) {
        // ---- Ensembl VEP (real-genome / full-scale alternative) ----------
        if ( params.download_vep_cache ) {
            ENSEMBLVEP_DOWNLOAD (
                params.vep_genome, params.vep_species, params.vep_cache_version
            )
            ch_vep_cache = ENSEMBLVEP_DOWNLOAD.out.cache.first()
            ch_versions  = ch_versions.mix( ENSEMBLVEP_DOWNLOAD.out.versions )
        }
        else {
            if ( !params.vep_cache ) {
                error "VEP annotation needs --vep_cache <dir> (or --download_vep_cache)."
            }
            ch_vep_cache = Channel.fromPath(params.vep_cache, checkIfExists: true).first()
        }

        ENSEMBLVEP_VEP (
            vcf, fasta, ch_vep_cache,
            params.vep_genome, params.vep_species, params.vep_cache_version
        )
        ch_versions   = ch_versions.mix( ENSEMBLVEP_VEP.out.versions.first() )
        ch_annot_vcf  = ENSEMBLVEP_VEP.out.vcf
        ch_report     = ENSEMBLVEP_VEP.out.report
    }
    else {
        // ---- SnpEff: downloaded cache (real genome) or offline build -----
        if ( params.download_snpeff_cache ) {
            SNPEFF_DOWNLOAD ( db )
            ch_db       = SNPEFF_DOWNLOAD.out.db.first()
            ch_versions = ch_versions.mix( SNPEFF_DOWNLOAD.out.versions )
        }
        else {
            SNPEFF_BUILD ( fasta, gff, db )
            ch_db       = SNPEFF_BUILD.out.db.first()
            ch_versions = ch_versions.mix( SNPEFF_BUILD.out.versions )
        }

        SNPEFF_ANN ( vcf, ch_db, db )
        ch_versions  = ch_versions.mix( SNPEFF_ANN.out.versions.first() )
        ch_annot_vcf = SNPEFF_ANN.out.vcf
        ch_report    = SNPEFF_ANN.out.report
    }

    // ---- H3: optional clinical + population evidence overlay -------------
    ANNOTATE_EVIDENCE ( ch_annot_vcf )
    ch_versions  = ch_versions.mix( ANNOTATE_EVIDENCE.out.versions )
    ch_final_vcf = ANNOTATE_EVIDENCE.out.vcf

    emit:
    vcf      = ch_final_vcf   // [ meta, vcf, tbi ]
    report   = ch_report      // [ meta, csv|html ]
    versions = ch_versions
}

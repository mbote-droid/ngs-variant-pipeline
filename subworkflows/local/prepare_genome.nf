//
// Build the reference indices the downstream stages need, once, up front:
// FASTA index (.fai), sequence dictionary (.dict), BWA-MEM2 index, and a
// bgzipped+tabixed known-sites VCF for BQSR. Outputs are value channels so a
// single reference is reused across every sample.
//

include { SAMTOOLS_FAIDX                 } from '../../modules/local/samtools_faidx'
include { GATK4_CREATESEQUENCEDICTIONARY } from '../../modules/local/gatk4_createsequencedictionary'
include { BWAMEM2_INDEX                  } from '../../modules/local/bwamem2_index'
include { TABIX_BGZIPTABIX              } from '../../modules/local/tabix_bgziptabix'

workflow PREPARE_GENOME {
    take:
    fasta        // channel: path(fasta)
    known_sites  // channel: path(known_sites) or empty

    main:
    ch_versions = Channel.empty()

    SAMTOOLS_FAIDX ( fasta )
    GATK4_CREATESEQUENCEDICTIONARY ( fasta )
    BWAMEM2_INDEX ( fasta )
    TABIX_BGZIPTABIX ( known_sites )

    ch_versions = ch_versions
        .mix( SAMTOOLS_FAIDX.out.versions )
        .mix( GATK4_CREATESEQUENCEDICTIONARY.out.versions )
        .mix( BWAMEM2_INDEX.out.versions )
        .mix( TABIX_BGZIPTABIX.out.versions )

    emit:
    fasta       = fasta.first()                          // value: path(fasta)
    fai         = SAMTOOLS_FAIDX.out.fai.first()         // value: path(fai)
    dict        = GATK4_CREATESEQUENCEDICTIONARY.out.dict.first()
    bwa_index   = BWAMEM2_INDEX.out.index.first()
    known_sites = TABIX_BGZIPTABIX.out.gz_tbi.first()    // value: [ gz, tbi ]
    versions    = ch_versions
}

//
// Read QC: FastQC on the raw reads, fastp for adapter/quality trimming, and a
// MultiQC report aggregating both. Emits the trimmed reads for downstream
// alignment (M2).
//

include { FASTQC  } from '../../modules/local/fastqc'
include { FASTP   } from '../../modules/local/fastp'
include { MULTIQC } from '../../modules/local/multiqc'

workflow FASTQ_QC {
    take:
    reads // channel: [ val(meta), [ path(reads) ] ]

    main:
    ch_versions   = Channel.empty()
    ch_multiqc_in = Channel.empty()

    FASTQC ( reads )
    ch_versions   = ch_versions.mix( FASTQC.out.versions.first() )
    ch_multiqc_in = ch_multiqc_in.mix( FASTQC.out.zip.map { meta, zip -> zip } )

    FASTP ( reads )
    ch_versions   = ch_versions.mix( FASTP.out.versions.first() )
    ch_multiqc_in = ch_multiqc_in.mix( FASTP.out.json.map { meta, json -> json } )

    MULTIQC ( ch_multiqc_in.collect() )
    ch_versions = ch_versions.mix( MULTIQC.out.versions )

    emit:
    trimmed_reads  = FASTP.out.reads   // channel: [ val(meta), [ path(reads) ] ]
    multiqc_report = MULTIQC.out.report
    versions       = ch_versions
}

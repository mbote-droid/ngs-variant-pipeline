//
// Validate the samplesheet and turn it into a channel of [ meta, [fastqs] ].
//

include { SAMPLESHEET_CHECK } from '../../modules/local/samplesheet_check'

workflow INPUT_CHECK {
    take:
    samplesheet // path: input samplesheet CSV

    main:
    ch_versions = Channel.empty()

    SAMPLESHEET_CHECK ( samplesheet )
    ch_versions = ch_versions.mix( SAMPLESHEET_CHECK.out.versions )

    reads = SAMPLESHEET_CHECK.out.csv
        .splitCsv ( header: true, sep: ',' )
        .map { row -> create_fastq_channel(row) }

    emit:
    reads                        // channel: [ val(meta), [ path(reads) ] ]
    versions = ch_versions       // channel: [ path(versions.yml) ]
}

// Build a meta map + typed FASTQ file list from one normalized samplesheet row.
def create_fastq_channel(LinkedHashMap row) {
    def meta = [:]
    meta.id         = row.sample
    meta.single_end = row.single_end.toBoolean()
    meta.status     = (row.status ?: '0').toInteger()

    if (meta.single_end) {
        return [ meta, [ file(row.fastq_1, checkIfExists: true) ] ]
    }
    return [ meta, [ file(row.fastq_1, checkIfExists: true),
                     file(row.fastq_2, checkIfExists: true) ] ]
}

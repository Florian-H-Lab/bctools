#!/usr/bin/env python

tool_description = """
Exract barcodes from a FASTQ file according to a user-specified pattern.
By default output is written to stdout.

Example usage:
- move nucleotides at positions 1-3 and 6-7 to FASTQ header and write to file output.fastq:
fastq_exract_barcodes.py barcoded_input.fastq XXXNNXX --out output.fastq
"""

# status: testing
# * proposed features:
#     * transparently read fastq.gz files?
#     * option to write fastq.gz files?
#     * annotate extracted sequence in header?
#     * option not to write to the header?
#     * ability to read fastq from stdin?
#     * option to skip barcoded reads containing unspecified N nuclotide in barcode?

import argparse
import logging
import re
from sys import stdout
from Bio.SeqIO.QualityIO import FastqGeneralIterator

# avoid ugly python IOError when stdout output is piped into another program
# and then truncated (such as piping to head)
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

# parse command line arguments
parser = argparse.ArgumentParser(description=tool_description)

# positional arguments
parser.add_argument(
    "infile",
    help="Path to fastq file.")
parser.add_argument(
    "pattern",
    help="Pattern of barcode nucleotides starting at 5'-end. X positions will be moved to the header, N positions will be kept.")
# optional arguments
parser.add_argument(
    "-o", "--outfile",
    help="Write results to this file.")
parser.add_argument(
    "-b", "--bcs",
    dest="out_bc_fasta",
    help="If set, barcodes are written to this file in FASTA format.")
parser.add_argument(
    "-v", "--verbose",
    help="Be verbose.",
    action="store_true")
parser.add_argument(
    "-d", "--debug",
    help="Print lots of debugging information",
    action="store_true")

args = parser.parse_args()
if args.debug:
    logging.basicConfig(level=logging.DEBUG)
elif args.verbose:
    logging.basicConfig(level=logging.INFO)
logging.info("Parsed arguments:")
logging.info("  infile: '{}'".format(args.infile))
logging.info("  pattern: '{}'".format(args.pattern))
if args.outfile:
    logging.info("  outfile: enabled writing to file")
    logging.info("  outfile: '{}'".format(args.outfile))
if args.out_bc_fasta:
    logging.info("  bcs: enabled writing barcodes to fasta file")
    logging.info("  bcs: {}".format(args.out_bc_fasta))
logging.info("")

# check if supplied pattern is valid
valid_pattern = re.compile("^[XN]+$")
pattern_match = valid_pattern.match(args.pattern)
if pattern_match is None:
    raise ValueError("Error: supplied pattern '{}' is not valid.".format(args.pattern))

# check if at least one barcode position is included in the pattern
has_bcpos_pattern = re.compile("X")
pattern_match = has_bcpos_pattern.search(args.pattern)
if pattern_match is None:
    raise ValueError("Error: supplied pattern '{}' does not contain a barcode position 'X'.".format(args.pattern))

logging.info("Barcode pattern analysis:")
# get X positions of pattern string
barcode_nt_pattern = re.compile("X+")
barcode_positions = []
for m in re.finditer(barcode_nt_pattern, args.pattern):
    logging.info('  found barcode positions in pattern: %02d-%02d: %s' % (m.start(), m.end(), m.group(0)))
    barcode_positions.append((m.start(), m.end()))
logging.info("  barcode positions: {}".format(barcode_positions))
# get last position of a barcode nt in the pattern
# reads must be long enough for all
min_readlen = barcode_positions[-1][-1]
logging.info("  last position of a barcode nt in pattern: {}".format(min_readlen))
logging.info("")

# get coordinates of nucleotides to keep
# the tail after the last barcode nt is handled separately
seq_positions = []
last_seq_start = 0
for bcstart, bcstop in barcode_positions:
    seq_positions.append((last_seq_start, bcstart))
    last_seq_start = bcstop
logging.info("  sequence positions: {}".format(seq_positions))
logging.info("  start of sequence tail: {}".format(last_seq_start))

samout = (open(args.outfile, "w") if args.outfile is not None else stdout)
if args.out_bc_fasta is not None:
    faout = open(args.out_bc_fasta, "w")
for header, seq, qual in FastqGeneralIterator(open(args.infile)):

    # skip reads that are too short to extract the full requested barcode
    if len(seq) < min_readlen:
        logging.warning("skipping read '{}', is too short to extract the full requested barcode".format(header))
        logging.debug("seq: {}".format(seq))
        logging.debug("len(seq): {}".format(len(seq)))
        continue

    # extract barcode nucleotides
    barcode_list = []
    for bcstart, bcstop in barcode_positions:
        barcode_list.append(seq[bcstart:bcstop])
    barcode = "".join(barcode_list)
    logging.debug("extracted barcode: {}".format(barcode))

    # create new sequence and quality string without barcode nucleotides
    new_seq_list = []
    new_qual_list = []
    for seqstart, seqstop in seq_positions:
        new_seq_list.append(seq[seqstart:seqstop])
        new_qual_list.append(qual[seqstart:seqstop])
    new_seq_list.append(seq[last_seq_start:])
    new_qual_list.append(qual[last_seq_start:])
    new_seq = "".join(new_seq_list)
    new_qual = "".join(new_qual_list)
    # check if at least one nucleotide is left. having none would break fastq
    if len(new_seq) == 0:
        logging.warning("skipping read '{}', no sequence remains after barcode extraction".format(header))
        logging.debug("seq: {}".format(seq))
        logging.debug("len(seq): {}".format(len(seq)))
        continue

    # write barcode nucleotides into header
    annotated_header = header + " " + barcode
    samout.write("@%s\n%s\n+\n%s\n" % (annotated_header, new_seq, new_qual))

    # write barcode to fasta if requested
    if args.out_bc_fasta is not None:
        faout.write(">{}\n{}\n".format(header, barcode))

# close files
samout.close()
if args.out_bc_fasta is not None:
    faout.close()

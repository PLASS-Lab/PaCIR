# Data Licenses and Attribution

## Scope

The root [MIT license](LICENSE) applies to PaCIR code in `code/`.
Author-created documentation, numerical input transformations, and experimental results are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), attributed to
Yeongseop Lee, ChanSung Jung, and Yunsik Son (2026). These results include
`expected.json`, `data/design.json`, `data/selection.json.gz`, the recorded
tasks in `data/*.jsonl.gz`, and `data/callhome-reference-risks.json.gz`.
This grant covers the authors' contributions, not third-party source material.

`data/inputs.json.gz` contains transformed inputs identified by `domain`.
The source terms below apply to the corresponding records. PaCIR transforms
source information into candidate sets, reference partitions, risk labels,
and relation packets, with window-local integer candidate IDs.

## Switchboard (`switchboard`)

Source: [ISIP MS98 Switchboard transcripts](https://isip.piconepress.com/projects/switchboard/),
29 January 2003 release. The [OpenSLR SLR5 mirror](https://www.openslr.org/5/)
identifies these Mississippi State transcripts and lexicon as **Unrestricted**.
The included records are PaCIR's derived numerical inputs, not transcriptions
or audio.

## Ubuntu IRC (`irc` and `data/irc.json.gz`)

Source: Kummerfeld et al. (2019),
[A Large-Scale Corpus for Conversation Disentanglement](https://doi.org/10.18653/v1/P19-1374).
The [source dataset](https://github.com/jkkummerfeld/irc-disentanglement)
is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
its [license text](https://github.com/jkkummerfeld/irc-disentanglement/blob/master/data/LICENSE-data.txt)
is provided by the original authors. PaCIR derives candidate sets, relation
packets, and numeric linkage labels and adds its own predictions and measurements.
Message text and user names are not included.

## TAB (`tab`)

Source: [Text Anonymization Benchmark](https://github.com/NorskRegnesentral/text-anonymization-benchmark),
[dataset paper](https://doi.org/10.1162/coli_a_00458).
PaCIR derives numerical candidate sets and partitions from the annotations;
the underlying court judgments are not included. The source repository's
[MIT notice](https://github.com/NorskRegnesentral/text-anonymization-benchmark/blob/master/LICENSE.txt)
is retained below.

> The MIT License (MIT)
>
> Copyright (C) 2021-2026 Norsk Regnesentral
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## MITRE Enterprise ATT&CK (`attack`)

Source: [Enterprise ATT&CK v19.2](https://github.com/mitre/cti/tree/8543c5b05bd9bbcace9fc37f30bba96b675b6f33/enterprise-attack),
commit `8543c5b05bd9bbcace9fc37f30bba96b675b6f33`.
PaCIR transforms technique-group links into candidate sets and ordered cues.
The [source license and notice](https://github.com/mitre/cti/blob/8543c5b05bd9bbcace9fc37f30bba96b675b6f33/LICENSE.txt)
for ATT&CK are reproduced below.

> The MITRE Corporation (MITRE) hereby grants you a non-exclusive, royalty-free license to use ATT&CK® for research,
> development, and commercial purposes. Any copy you make for such purposes is authorized provided that you reproduce
> MITRE's copyright designation and this license in any such copy.
>
> "© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation."
>
> MITRE does not claim ATT&CK enumerates all possibilities for the types of actions and behaviors documented as part
> of its adversary model and framework of techniques. Using the information contained within ATT&CK to address or
> cover full categories of techniques will not guarantee full defensive coverage as there may be undisclosed techniques
> or variations on existing techniques not documented by ATT&CK.
>
> ALL DOCUMENTS AND THE INFORMATION CONTAINED THEREIN ARE PROVIDED ON AN "AS IS" BASIS AND THE CONTRIBUTOR, THE
> ORGANIZATION HE/SHE REPRESENTS OR IS SPONSORED BY (IF ANY), THE MITRE CORPORATION, ITS BOARD OF TRUSTEES, OFFICERS,
> AGENTS, AND EMPLOYEES, DISCLAIM ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTY THAT THE
> USE OF THE INFORMATION THEREIN WILL NOT INFRINGE ANY RIGHTS OR ANY IMPLIED WARRANTIES OF MERCHANTABILITY OR FITNESS
> FOR A PARTICULAR PURPOSE.

## CallHome results (`callhome`)

Source: Linguistic Data Consortium (2008),
[CABank English CallHome Corpus](https://doi.org/10.21415/T5KP54).
Only PaCIR's recorded risk labels and experimental measurements are included;
CABank-derived candidate sets, reference partitions, and relation packets are
excluded. Access to the original corpus is governed by
[TalkBank's terms](https://talkbank.org/0share/rules.html).

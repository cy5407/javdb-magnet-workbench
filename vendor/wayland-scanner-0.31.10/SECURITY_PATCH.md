# Local security compatibility patch

Source: wayland-scanner 0.31.10 from crates.io, MIT licensed.

Changes:

- raise quick-xml from 0.39 to 0.41;
- use BytesRef::decode() for an XML general-reference name, whose grammar
  cannot contain line endings.

This removes RUSTSEC-2026-0194 and RUSTSEC-2026-0195 while retaining the
upstream wayland-scanner API. Remove this patch after upstream publishes a
compatible release that uses quick-xml 0.41 or newer.

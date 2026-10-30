# Reference documents

Vendor documents used for the EKMBDXB7V1 implementation and the CoolMaster comparison. Downloaded on 2026-10-30. Files are unmodified; copyright remains with their publishers and the repository's software license does not apply to them.

These are the public revisions we found, not confirmation of what the latest firmware supports. The DTA116A51, EKMBDXB and CoolMaster maps describe different adapters. Do not treat their registers as interchangeable.

## Manuals and specifications

| Local copy | Revision and scope | Original source |
| --- | --- | --- |
| [DTA116A51 engineering manual](EDMT721419-DTA116A51.pdf) | EDMT721419; includes functional specification CB13A033, first edition 2013-08-09. Historical reference for the older adapter. | [Daikin](https://daikincomfort.com/docs/default-source/general/vrv/em-edmt721419.pdf) |
| [DTA116A51 product flyer](DTA116A51-product-flyer.pdf) | PF-DIINET-11_15. Lists 16 indoor units and 2 outdoor units. | [Daikin](https://daikinac.com/docs/default-source/general/vrv/pf-diiinet.pdf) |
| [EKMBDXB design guide](EKMBDXB-design-guide-4P642495-1A.pdf) | EKMBDXB7V1, 4P642495-1A, 2022.02. Primary reference for the current integration: register map, communication and software-update procedures. | [Daikin](https://www.daikin-ce.com/content/dam/document-library/Installer-reference-guide/ac/vrv/ekmbdxb/EKMBDXB_Design%20guide_4PEN642495-1A_English.pdf) |
| [EKMBDXB installation manual](EKMBDXB-installation-manual-4P635058-1B.pdf) | 4P635058-1B, 2022.02. Wiring and installation. | [Daikin](https://www.daikin.co.uk/content/dam/document-library/installation-manuals/opt-and-acc/controls/ekmbdxb/EKMBDXB_Installation%20manual_4PEN635058-1B_English.pdf) |
| [Earlier EKMBDXB installation manual](EKMBDXB-installation-manual-4P635058-1.pdf) | 4P635058-1, 2020.10. Earlier revision still linked from the product page; retained for comparison. | [Daikin](https://www.daikin.co.uk/content/dam/document-library/installation-manuals/opt-and-acc/controls/ekmbdxb/EKMBDXB_4PEN635058-1_Installation%20manual_English.pdf) |
| [CoolMaster programmer reference](CoolMaster-programmer-reference-0.10.pdf) | Revision 0.10; cover date printed as 11/1/2024. CoolMaster product-line ASCII commands. | [CoolAutomation](https://support.coolautomation.com/hc/en-us/article_attachments/17317574262557) |
| [CoolMaster user manual](CoolMaster-user-manual-1.4.pdf) | Document 1.4, firmware 1.0.0. Touchscreen controls and configuration. | [CoolAutomation](https://support.coolautomation.com/hc/en-us/article_attachments/10558874317853/CoolMaster_UM_v1.4.pdf) |
| [CoolAutomation Modbus integration guidelines](CoolAutomation-Modbus-integration-guidelines-1.3.pdf) | Revision 1.3, 2025-07-17. CoolMaster/CooLink Modbus interfaces, distinct from Daikin's adapters. | [CoolAutomation](https://support.coolautomation.com/hc/en-us/article_attachments/12455777507485/CoolAutomation-Modbus-integration-guidelines.pdf) |

## Driver guides

These HTML snapshots preserve the publishers' descriptions, not independent hardware verification. External images and other linked assets are not bundled.

| Local copy | Scope | Original source |
| --- | --- | --- |
| [4Drivers DTA116A51 guide](4Drivers-DTA116A51-guide.html) | Driver version 1100. Claims four groups/64 addresses for DTA116A51 or newer compatible boards. | [4Drivers](https://site.4drivers.com.br/docs/Daikin_DTA/index_en.html) |
| [TapHome DTA116A51 guide](TapHome-DTA116A51-guide.html) | Page marked updated 03.2026. Describes a 16-unit implementation. | [TapHome](https://taphome.com/en/compatibility/daikin-dta116a51-vrv/) |

SHA-256 digests for all archived PDFs and HTML files are in [SHA256SUMS](SHA256SUMS). From this directory, run `sha256sum -c SHA256SUMS` to check them.

## Documentation gaps

The [comparison and evidence request](https://chatgpt.com/space/page_b6bf37b8ba308191b61f0df657412d0b) asks for a report tested on identified hardware and firmware, and for Daikin's latest functional specification, firmware release notes and feature-by-firmware register map. Both remain outstanding.

The [Daikin Reiri FAQ](https://www.daikin-solutions.com/faq) specifies 16 indoor units for DTA116A51. A [reported DTA116A51 installation](https://github.com/martinstafford/daikin_d3net/issues/3#issuecomment-2924704985) contains readings for group 2. That discrepancy needs confirmation against the exact board and firmware.

The older [Daikin Singapore D'Smart catalogue](https://www.daikin.com.sg/resources/ck/files/catalogue/D%27Smart%20Series%20Catalogue.pdf) appeared in search results with a 64-unit claim, but its download returned HTTP 404. No local copy is included, and the search excerpt is not used as a verified specification.

The [online CoolMaster programmer reference](https://support.coolautomation.com/hc/en-us/articles/7068465434397-CoolMaster-PRM-Programmers-Reference-Manual) was readable through web search but blocked direct HTML download with HTTP 403. Its downloadable PDF is archived above; the two versions are not assumed identical.

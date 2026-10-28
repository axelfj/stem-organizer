# Publishing on the Microsoft Store

The Store signs the app itself, so Windows users install it with no
SmartScreen warning. GitHub Actions builds the package
(`StemOrganizer-MicrosoftStore` artifact, `StemOrganizer.msix`) on every push.

## One-time setup

1. Create a free individual developer account at
   <https://storedeveloper.microsoft.com> and sign in to Partner Center.
2. *Apps and games > New product > MSIX or PWA app*, reserve the name
   **Stem Organizer**.
3. Open *Product management > Product identity* and copy three values into
   this repository's *Settings > Secrets and variables > Actions > Variables*:

   | Partner Center field | Repository variable |
   |---|---|
   | Package/Identity/Name | `MSIX_IDENTITY_NAME` |
   | Package/Identity/Publisher | `MSIX_PUBLISHER` |
   | Package/Properties/PublisherDisplayName | `MSIX_PUBLISHER_DISPLAY_NAME` |

4. Re-run the *Build installers* workflow so the package carries your identity.

## Each release

1. Push a tag like `v0.1.0`. The package version becomes `0.1.0.0`.
2. Download `StemOrganizer.msix` from the workflow run.
3. In Partner Center, start a submission and upload it under *Packages*.
   Fill in pricing (free), age rating, a description and screenshots, and
   a privacy policy URL (the app collects no data; a page saying so is enough).
4. Submit. Certification usually takes a few days.

The Store requires every new submission to have a higher version than the
last one, so always tag a new version before submitting.

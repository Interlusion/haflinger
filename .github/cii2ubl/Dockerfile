# phax's converter en16931-cii2ubl, which the conformance tests run (scripts/cii2ubl.sh); a
# Dockerfile, so Dependabot keeps the image's pin current. phax publishes the converter's command
# line as a jar on Maven Central: it is pinned here by its SHA-256 and updated by hand (development
# guide).
FROM eclipse-temurin:21.0.12.1_1-jre-noble@sha256:cd35bb33859641c5374415826a5951845104093eaa401cbe9d3d9023444f1c13
# Into /opt, which the image has: ADD's --chmod would apply to a directory it creates too.
ADD --checksum=sha256:eb349dc57333d43bbe210d698ff97f6cf9b32e7a626910676581fb321d52ad46 --chmod=644 https://repo1.maven.org/maven2/com/helger/en16931-cii2ubl-cli/4.0.3/en16931-cii2ubl-cli-4.0.3-shaded.jar /opt/cii2ubl.jar
# Its own expansion of wildcards in file names walks the whole file system, /proc included, so it
# takes the names as they are. The edition and its output's names are pinned, so that a new
# release can't change them unseen: 2017, CII D16B to UBL 2.1, rather than the one it chooses by
# each file's BT-24, and <name>-ubl.xml, its default, which the tests expect. Its heap stays under
# 100 MB in the conformance tests. `timeout` ends it before the tests give up waiting, which would
# stop only the docker client.
ENTRYPOINT ["timeout", "120", "java", "-XX:MaxRAMPercentage=60", "-jar", "/opt/cii2ubl.jar", "--disable-wildcard-expansion", "--en-version", "2017", "--output-suffix", "-ubl"]

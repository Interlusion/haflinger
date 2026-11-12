# KoSIT's validator with KoSIT's XRechnung configuration, which the conformance tests run
# (scripts/kosit-validator.sh); a Dockerfile, so Dependabot keeps the images' pins current. KoSIT
# publishes the validator as a jar and the configuration as a ZIP, neither with a checksum: each is
# pinned here by its SHA-256 and updated by hand (development guide). The configuration is the
# release Haflinger vendors, whole, as the validator needs its report stylesheets too
# (tests/unit/test_vendoring.py checks they agree).
FROM busybox:1.37.0@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec AS configuration
ADD --checksum=sha256:2530cd107c414511c5d0462ec10f886910395abfca820db82e83d70bf01221a8 https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/v2026-08-31/xrechnung-3.0.2-validator-configuration-2026-08-31.zip /configuration.zip
RUN mkdir /configuration && unzip -q /configuration.zip -d /configuration && chmod -R a+rX /configuration

FROM eclipse-temurin:21.0.12.1_1-jre-noble@sha256:cd35bb33859641c5374415826a5951845104093eaa401cbe9d3d9023444f1c13
COPY --from=configuration /configuration /opt/kosit/configuration
# Into the directory COPY made: ADD's --chmod would apply to a directory it creates too.
ADD --checksum=sha256:799e64befca97d4080e03608c80b85dd5a5ecc5f4ae4f35d1116ec2855b9a7c9 --chmod=644 https://github.com/itplr-kosit/validator/releases/download/v1.6.3/validator-1.6.3-standalone.jar /opt/kosit/validator.jar
# Three fifths of the container's memory for the heap, where Java takes a quarter by default, the
# rest for Java itself: the validator keeps every report until it ends, so it needs more with each
# document: in the conformance tests, about 600 MB for the call with 258 and 750 MB for the one
# with 524. `timeout` ends it before the tests give up waiting, which would stop only the docker
# client.
ENTRYPOINT ["timeout", "220", "java", "-XX:MaxRAMPercentage=60", "-jar", "/opt/kosit/validator.jar", "-s", "/opt/kosit/configuration/scenarios.xml", "-r", "/opt/kosit/configuration"]

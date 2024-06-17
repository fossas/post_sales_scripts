The Python script converts the CSV data into a fossa-deps.yml file with remote-dependencies.
The CSV contains URLs like:

https://github.com/COVESA/vsomeip/archive/refs/heads/master.zip,
https://github.com/boostorg/boost/archive/refs/tags/boost-1.55.0.zip,
https://github.com/protocolbuffers/protobuf/tree/v21.12,
https://github.com/openssl/openssl/archive/refs/heads/openssl-3.0.zip,
https://github.com/eerimoq/pbtools/archive/refs/tags/0.47.0.zip,
https://github.com/COVESA/dlt-daemon,
https://github.com/c-ares/c-ares

Because referenced-dependencies needs a URL of archived source code ( zip file). If the Git URL does not have a .zip at the end; the scrip adds "zipball/master" at the end ot the URL.

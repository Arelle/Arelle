# Use oldest release with standard support for linked glibc compatibility
FROM ubuntu:22.04

ARG OPENSSL_VERSION
ARG PYTHON_VERSION
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV DEBIAN_FRONTEND=noninteractive
ENV SSL_CERT_DIR=/etc/ssl/certs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update -y && \
    apt-get dist-upgrade -y && \
    apt-get install -y \
        build-essential \
        curl \
        git \
        libbz2-dev \
        libffi-dev \
        libgdbm-compat-dev \
        libgdbm-dev \
        liblzma-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libnss3-dev \
        libreadline-dev \
        libsqlite3-dev \
        libtk8.6 \
        libxml2-dev \
        libxmlsec1-dev \
        llvm \
        make \
        tk-dev \
        unixodbc-dev \
        uuid-dev \
        wget \
        xz-utils \
        zlib1g-dev

WORKDIR /tmp

RUN wget https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz \
    && tar xzf openssl-${OPENSSL_VERSION}.tar.gz \
    && (cd openssl-${OPENSSL_VERSION} \
        && ./config \
            -fPIC \
            --openssldir=/usr/local/ssl \
            --prefix=/usr/local \
            --libdir=lib \
            shared \
        && make --jobs "$(nproc)" \
        && make install_sw \
        && ldconfig) \
    && rm -r ./openssl-${OPENSSL_VERSION} \
    && rm ./openssl-${OPENSSL_VERSION}.tar.gz

ENV TCLTK_CFLAGS="-I/usr/include/tcl8.6"
ENV TCLTK_LIBS="-ltcl8.6 -ltk8.6"

RUN wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
    && tar xzf Python-${PYTHON_VERSION}.tgz \
    && (cd Python-${PYTHON_VERSION} \
        && export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH \
        && export LDFLAGS="-L/usr/local/lib" \
        && export CPPFLAGS="-I/usr/local/include" \
        && ./configure \
            --enable-optimizations \
            --enable-shared \
            --with-computed-gotos \
            --with-lto \
            --with-openssl=/usr/local \
            --with-openssl-rpath=auto \
        && make --jobs "$(nproc)" \
        && make install) \
    && rm -r ./Python-${PYTHON_VERSION} \
    && rm ./Python-${PYTHON_VERSION}.tgz

RUN pip3 install --upgrade pip setuptools wheel

WORKDIR /build

ADD requirements*.txt .

RUN pip3 install -r requirements-build.txt

ADD . /build

RUN /bin/sh ./scripts/buildLinuxDist.sh ubuntu

ENTRYPOINT ["/bin/sh", "-c"]

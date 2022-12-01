# Use oldest LTS release for linked glibc compatibility
FROM registry.access.redhat.com/ubi7:7.9

ARG OPENSSL_VERSION
ARG PYTHON_VERSION
ARG TCLTK_VERSION
ENV LD_LIBRARY_PATH=/usr/local/lib

RUN yum -y update \
    && yum -y install \
        bzip2-devel \
        gcc \
    	gcc-c++ \
        gdbm-devel \
        git \
        libffi-devel \
        libuuid-devel \
        libX11-devel \
        libxml2-devel \
        libxslt-devel \
    	make \
        ncurses-devel \
        readline-devel \
        sqlite-devel \
        unixODBC-devel \
        wget \
    && yum autoremove -y \
    && yum clean all \
    && rm -rf /var/cache/yum

WORKDIR /tmp

RUN wget https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz \
    && tar xzf openssl-${OPENSSL_VERSION}.tar.gz \
    && (cd openssl-${OPENSSL_VERSION} \
        && ./config \
            -fPIC \
            --openssldir=/usr/local/ssl \
            --prefix=/usr/local \
            no-shared \
            no-ssl2 \
        && make \
        && make install --jobs "$(nproc)") \
    && rm -r ./openssl-${OPENSSL_VERSION} \
    && rm ./openssl-${OPENSSL_VERSION}.tar.gz

RUN wget https://sourceforge.net/projects/tcl/files/Tcl/${TCLTK_VERSION}/tcl${TCLTK_VERSION}-src.tar.gz \
    && tar xzf tcl${TCLTK_VERSION}-src.tar.gz \
    && (cd tcl${TCLTK_VERSION}/unix \
        && ./configure \
        && make install --jobs "$(nproc)") \
    && rm -r ./tcl${TCLTK_VERSION} \
    && rm tcl${TCLTK_VERSION}-src.tar.gz

RUN wget https://sourceforge.net/projects/tcl/files/Tcl/${TCLTK_VERSION}/tk${TCLTK_VERSION}-src.tar.gz \
    && tar xzf tk${TCLTK_VERSION}-src.tar.gz \
    && (cd tk${TCLTK_VERSION}/unix \
        && ./configure \
        && make install --jobs "$(nproc)") \
    && rm -r ./tk${TCLTK_VERSION} \
    && rm tk${TCLTK_VERSION}-src.tar.gz

RUN wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
    && tar xzf Python-${PYTHON_VERSION}.tgz \
    && (cd Python-${PYTHON_VERSION} \
        && ./configure \
            --enable-optimizations \
            --enable-shared \
            --with-computed-gotos \
            --with-openssl=/usr/local \
            --with-lto \
            --with-system-ffi \
        && make install --jobs "$(nproc)") \
    && rm -r ./Python-${PYTHON_VERSION} \
    && rm ./Python-${PYTHON_VERSION}.tgz

RUN pip3 install --upgrade pip setuptools wheel

WORKDIR /build

ADD ../requirements*.txt .

RUN pip3 install -r requirements-build.txt

ADD ../ /build

RUN /bin/sh ./scripts/buildLinuxDist.sh redhat

ENTRYPOINT ["/bin/sh", "-c"]

{
  pkgs ? import <nixpkgs> {},
  pythonPackages ? pkgs.python36Packages,
  forDev ? true
}:
{
  digitalMarketplaceSupplierFrontendEnv = pkgs.stdenv.mkDerivation {
    name = "digitalmarketplace-supplier-frontend-env";
    buildInputs = [
      pythonPackages.virtualenv
      pkgs.nodejs
      pkgs.libffi
      pkgs.libyaml
      # pip requires git to fetch some of its dependencies
      pkgs.git
      # for `cryptography`
      pkgs.openssl
    ] ++ pkgs.stdenv.lib.optionals forDev ([
        # for lxml
        pkgs.libxml2
        pkgs.libxslt
        # for frontend tests
        pkgs.phantomjs
      ] ++ pkgs.stdenv.lib.optionals pkgs.stdenv.isDarwin [
        # for watchdog... not that it works on darwin yet anyway, but it will/would need them
        pkgs.darwin.apple_sdk.frameworks.CoreServices
        pkgs.darwin.cf-private
      ]
    );

    hardeningDisable = pkgs.stdenv.lib.optionals pkgs.stdenv.isDarwin [ "format" ];

    VIRTUALENV_ROOT = "venv${pythonPackages.python.pythonVersion}";
    VIRTUAL_ENV_DISABLE_PROMPT = "1";
    SOURCE_DATE_EPOCH = "315532800";

    # if we don't have this, we get unicode troubles in a --pure nix-shell
    LANG="en_GB.UTF-8";

    shellHook = ''
      if [ ! -e $VIRTUALENV_ROOT ]; then
        ${pythonPackages.virtualenv}/bin/virtualenv $VIRTUALENV_ROOT
      fi
      source $VIRTUALENV_ROOT/bin/activate
      make requirements${pkgs.stdenv.lib.optionalString forDev "-dev"}
    '';
  };
}

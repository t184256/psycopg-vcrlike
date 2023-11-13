{
  description = "Something like pyvcr and python-recording, but for recording SQL queries.";

  inputs.pytest-icecream = {
    url = "github:t184256/pytest-icecream";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    let
      deps = pyPackages: with pyPackages; [
        aiofiles
        psycopg
        psycopg.pool
        pytest
        pytest-recording
        ruamel_yaml
      ];
      tools = pkgs: pyPackages: (with pyPackages; [
        pytestCheckHook pytest-asyncio pytest-postgresql
        mypy pytest-mypy
        pytest-postgresql
        pytest-recording aiohttp
        types-aiofiles
      ] ++ [pkgs.ruff]);
      devTools = pkgs: pyPackages: (with pyPackages; [
        pytest-icecream
      ]);

      psycopg-vcrlike-package = {pkgs, python3Packages}:
        python3Packages.buildPythonPackage {
          pname = "psycopg-vcrlike";
          version = "0.0.1";
          src = ./.;
          format = "pyproject";
          propagatedBuildInputs = deps python3Packages;
          nativeBuildInputs = [ python3Packages.setuptools ];
          checkInputs = tools pkgs python3Packages;
        };

      types-aiofiles-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            types-aiofiles = pyPrev.buildPythonPackage rec {
              pname = "types-aiofiles";
              version = "23.2.0.0";
              src = prev.fetchPypi {
                inherit pname version;
                hash = "sha256-tqcSe9Iy4IAlMoN7hBQLHNXfGe5gvqOlaZcg0rWDNhs=";
              };
            };
          })];
      };

      fresh-mypy-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            mypy =
              if prev.lib.versionAtLeast pyPrev.mypy.version "1.7.0"
              then pyPrev.mypy
              else pyPrev.mypy.overridePythonAttrs (_: {
                version = "1.7.0";
                patches = [];
                src = prev.fetchFromGitHub {
                  owner = "python";
                  repo = "mypy";
                  rev = "refs/tags/v1.7.0";
                  hash = "sha256-2GUEBK3e0GkLFaEg03iSOea2ubvAfcCtVQc06dcqnlE=";
                };
              });
          })];
      };

      overlay-psycopg-vcrlike = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            psycopg-vcrlike = final.callPackage psycopg-vcrlike-package {
              python3Packages = pyFinal;
            };
          })];
      };

      overlay = nixpkgs.lib.composeManyExtensions [
        overlay-psycopg-vcrlike
        types-aiofiles-overlay
      ];

      overlay-all = nixpkgs.lib.composeManyExtensions [
        inputs.pytest-icecream.overlays.default
        fresh-mypy-overlay
        overlay
      ];
    in
      flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = import nixpkgs { inherit system; overlays = [ overlay-all ]; };
          defaultPython3Packages = pkgs.python311Packages;  # force 3.11

          psycopg-vcrlike = pkgs.callPackage psycopg-vcrlike-package {
            python3Packages = defaultPython3Packages;
          };
        in
        {
          devShells.default = pkgs.mkShell {
            buildInputs = [(defaultPython3Packages.python.withPackages deps)];
            nativeBuildInputs = [
              (tools pkgs defaultPython3Packages)
              (devTools pkgs defaultPython3Packages)
            ];
            shellHook = ''
            export PYTHONASYNCIODEBUG=1
            #export PYTHONWARNINGS=error
            '';
          };
          packages.psycopg-vcrlike = psycopg-vcrlike;
          packages.default = psycopg-vcrlike;
        }
    ) // { overlays.default = overlay; };
}

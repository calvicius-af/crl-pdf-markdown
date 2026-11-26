from .cli import main

# A conversão arranca processos com «spawn», que voltam a importar este módulo:
# sem esta guarda, cada processo de conversão voltaria a correr a CLI.
if __name__ == "__main__":
    raise SystemExit(main())

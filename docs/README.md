# README - Documentação

## 📚 Visualizar a Documentação

### Opção 1: Instalar e Servir Localmente

```bash
# Instalar dependências
pip install -r docs-requirements.txt

# Servir documentação (modo desenvolvimento)
mkdocs serve

# Acessar em: http://127.0.0.1:8000
```

### Opção 2: Build Estático

```bash
# Gerar site estático
mkdocs build

# Os arquivos HTML estarão em: site/
```

---

## 🎨 Personalização

### Adicionar Páginas

1. Criar arquivo `.md` em `docs/`
2. Adicionar ao `nav` em `mkdocs.yml`

### Alterar Tema

Edite `mkdocs.yml`:

```yaml
theme:
  palette:
    primary: indigo  # Mudar cor primária
    accent: pink     # Mudar cor de destaque
```

---

## 📝 Sintaxe Markdown

A documentação suporta:

- ✅ Admonitions (info, warning, tip)
- ✅ Tabs
- ✅ Code highlighting
- ✅ Mermaid diagrams
- ✅ Emojis
- ✅ Tables

Exemplos: https://squidfunk.github.io/mkdocs-material/reference/

---

## 🚀 Deploy

### GitHub Pages

```bash
mkdocs gh-deploy
```

### Servidor Web

Copie a pasta `site/` para seu servidor web (Apache, Nginx, IIS).

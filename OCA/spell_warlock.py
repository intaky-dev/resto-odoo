import os
import asyncio
import aiohttp
import time
import logging
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

# Configuración
BASE_DIR = "./repos"
SYMLINK_DIR = "./modules"
CLONE_DEPTH = 1
LOG_FILE = "./log.txt"
COMBINED_REQUIREMENTS_FILE = "combined_requirements.txt"
MAX_WORKERS = 5  # Número máximo de repositorios a clonar simultáneamente
GITHUB_API_URL = 'https://api.github.com/orgs/OCA/repos'
MAX_CLONE_ATTEMPTS = 3  # Número máximo de intentos de clonación

# Configuración del logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Aumentar el buffer de Git
os.system('git config --global http.postBuffer 524288000')

class RepoCloner:
    def __init__(self, base_dir, symlink_dir, clone_depth, max_workers):
        self.base_dir = Path(base_dir).resolve()
        self.symlink_dir = Path(symlink_dir).resolve()
        self.clone_depth = clone_depth
        self.max_workers = max_workers
        self.repos = asyncio.run(self.get_oca_repos())

        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.symlink_dir, exist_ok=True)

    async def fetch_page(self, session, page):
        async with session.get(f'{GITHUB_API_URL}?page={page}&per_page=100') as response:
            if response.status == HTTPStatus.OK:
                return await response.json()
            elif response.status == HTTPStatus.FORBIDDEN:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                sleep_time = max(0, reset_time - int(time.time()))
                logging.info(f"Límite de tasa alcanzado. Esperando {sleep_time} segundos antes de continuar...")
                time.sleep(sleep_time)
                return await self.fetch_page(session, page)
            else:
                logging.error(f"Error al obtener los repositorios: {response.status}")
                return []

    async def get_oca_repos(self):
        # Obtén la lista de repositorios de la organización OCA en GitHub
        repos = []
        page = 1
        async with aiohttp.ClientSession() as session:
            while True:
                logging.info(f"Obteniendo repositorios de la página {page}...")
                page_repos = await self.fetch_page(session, page)
                if page_repos:
                    repos += page_repos
                    page += 1
                else:
                    break
        return [repo['clone_url'] for repo in repos]

    async def clone_repo(self, repo_url, attempt=1):
        # Clona un repositorio. Si falla, reintenta después de un breve retraso.
        try:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            clone_dir = self.base_dir / repo_name
            if not clone_dir.exists():
                logging.info(f"Clonando el repositorio {repo_url}...")
                start_time = time.time()
                if self.clone_depth is None:
                    process = await asyncio.create_subprocess_exec('git', 'clone', '--progress', repo_url, str(clone_dir), stdout=asyncio.subprocess.PIPE)
                else:
                    process = await asyncio.create_subprocess_exec('git', 'clone', '--progress', '--depth', str(self.clone_depth), repo_url, str(clone_dir), stdout=asyncio.subprocess.PIPE)
                await process.communicate()
                end_time = time.time()
                logging.info(f"Repositorio {repo_url} clonado exitosamente en {end_time - start_time} segundos.")
            else:
                logging.info(f"El repositorio {repo_url} ya ha sido clonado.")
        except Exception as e:
            if attempt < MAX_CLONE_ATTEMPTS:
                logging.error(f"Error al clonar el repositorio {repo_url} en el intento {attempt}: {str(e)}. Reintentando...")
                time.sleep(5)  # Espera 5 segundos antes de reintentar
                await self.clone_repo(repo_url, attempt + 1)
            else:
                logging.error(f"Error al clonar el repositorio {repo_url} después de {MAX_CLONE_ATTEMPTS} intentos: {str(e)}")

    async def clone_all_repos(self):
        # Clona todos los repositorios usando un pool de trabajadores para limitar el número de operaciones simultáneas.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = [self.clone_repo(repo_url) for repo_url in self.repos]
            for future in asyncio.as_completed(tasks):
                await future

    def create_symlinks(self):
        # Crea enlaces simbólicos para todos los repositorios.
        for repo_url in self.repos:
            try:
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                source_dir = self.base_dir / repo_name
                dest_dir = self.symlink_dir / repo_name
                if not dest_dir.exists():
                    relative_path = os.path.relpath(source_dir, start=self.symlink_dir)
                    os.symlink(relative_path, dest_dir)
                    logging.info(f"Enlace simbólico creado para {repo_url}")
                else:
                    logging.info(f"El enlace simbólico para {repo_url} ya existe.")
            except Exception as e:
                logging.error(f"Error al crear el enlace simbólico para {repo_url}: {str(e)}")

    def run(self):
        # Ejecuta el script.
        asyncio.run(self.clone_all_repos())
        self.create_symlinks()

class RequirementsCombiner:
    def __init__(self, base_dir, combined_requirements_file):
        self.base_dir = Path(base_dir).resolve()
        self.combined_requirements_file = Path(combined_requirements_file).resolve()
        self.requirements_files = self.find_requirements_files()

    def find_requirements_files(self):
        # Busca todos los archivos de requisitos en los repositorios clonados.
        requirements_files = []
        for repo_dir in self.base_dir.iterdir():
            requirements_files += list(repo_dir.rglob('requirements.txt'))
        return requirements_files

    def combine_requirements(self):
        # Combina todos los archivos de requisitos en un solo archivo.
        requirements = defaultdict(int)
        for req_file in self.requirements_files:
            try:
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            requirements[line] += 1
                logging.info(f"Requisitos de {req_file} añadidos.")
            except Exception as e:
                logging.error(f"Error al leer el archivo de requisitos {req_file}: {str(e)}")
        try:
            with open(self.combined_requirements_file, 'w') as f:
                for requirement, count in sorted(requirements.items()):
                    f.write(requirement + '\n')
            logging.info(f"Archivo de requisitos combinados creado: {self.combined_requirements_file}")
        except Exception as e:
            logging.error(f"Error al crear el archivo de requisitos combinados: {str(e)}")

    def run(self):
        # Ejecuta el script.
        self.combine_requirements()

cloner = RepoCloner(BASE_DIR, SYMLINK_DIR, CLONE_DEPTH, MAX_WORKERS)
cloner.run()

combiner = RequirementsCombiner(BASE_DIR, COMBINED_REQUIREMENTS_FILE)
combiner.run()

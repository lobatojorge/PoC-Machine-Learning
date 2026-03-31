import os
import time
import shutil
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("InspectorDatos")

class DataInspectorAgent:
    """
    Agente enfocado EXCLUSIVAMENTE en Data Observability.
    Responsabilidad única: Asegurar que la materia prima no contenga anomalías silentes.
    """
    def __init__(self, raw_dir: str, quarantine_dir: str, processed_dir: str):
        self.raw_dir = raw_dir
        self.quarantine_dir = quarantine_dir
        self.processed_dir = processed_dir
        self.inspected_files = set()
        
        logger.info("El Inspector de Datos está en línea. Monitorizando pipeline de entrada.")

    def monitor_raw_zone(self):
        """Monitoriza el directorio de captación (ej. extracciones del sistema SIRENO)."""
        logger.info(f"Escuchando eventos en: {self.raw_dir}...")
        try:
            while True:
                for filename in os.listdir(self.raw_dir):
                    if filename.endswith(".csv") and filename not in self.inspected_files:
                        self._process_file(filename)
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Inspector apagado.")

    def _process_file(self, filename: str):
        filepath = os.path.join(self.raw_dir, filename)
        logger.info(f"Interceptado nuevo archivo: {filename}. Iniciando validación forense.")
        
        is_valid, errors = self._validate_data_contracts(filepath)
        
        if is_valid:
            self._route_to_processed(filepath, filename)
        else:
            self._route_to_quarantine(filepath, filename, errors)
            
        self.inspected_files.add(filename)

    def _validate_data_contracts(self, filepath: str) -> Tuple[bool, List[str]]:
        """
        Aplica reglas estrictas de dominio. 
        En producción, esto sería un wrapper sobre Great Expectations o Pandera.
        """
        logger.info("Aplicando reglas de data observability...")
        errors = []
        
        # --- PSEUDO-CÓDIGO EXPECTATIONS ---
        # df = pd.read_csv(filepath)
        
        # Expectativa 1: Pesos lógicos del Salmón
        # if df['peso_kg'].max() > 40.0:
        #     errors.append("Violación biométrica: Peso excede el máximo biológicamente posible (>40kg).")
        
        # Expectativa 2: Fechas coherentes (2004-2020)
        # if not df['fecha_campaña'].between('2004-01-01', '2020-12-31').all():
        #     errors.append("Violación temporal: Fechas fuera del marco cronológico del estudio (2004-2020).")

        # Para simular nuestro esqueleto, supondremos una validación satisfactoria.
        # Modificar a 'False' para simular un rechazo.
        is_clean = True 
        
        return is_clean, errors

    def _route_to_processed(self, filepath: str, filename: str):
        """Certifica el dataset y lo habilita para el resto de agentes/modelos."""
        dest_path = os.path.join(self.processed_dir, filename)
        logger.info(f"CERTIFICADO: Datos limpios. Promoviendo a zona de procesamiento: {dest_path}")
        # shutil.copy(filepath, dest_path)

    def _route_to_quarantine(self, filepath: str, filename: str, errors: List[str]):
        """Aísla los datos corruptos para análisis forense humano."""
        dest_path = os.path.join(self.quarantine_dir, filename)
        logger.error(f"CONTAMINACIÓN DETECTADA. Relegando a cuarentena: {dest_path}")
        
        report_path = os.path.join(self.quarantine_dir, f"{filename}_INSPECTION_ERRORS.log")
        with open(report_path, 'w') as f:
            f.write("--- REPORTE DE RECHAZO FORENSE ---\n")
            f.write("\n".join(errors))

if __name__ == "__main__":
    inspector = DataInspectorAgent(
        raw_dir=os.path.join("data", "raw"),
        quarantine_dir=os.path.join("data", "quarantine"),
        processed_dir=os.path.join("data", "processed")
    )
    # inspector.monitor_raw_zone()

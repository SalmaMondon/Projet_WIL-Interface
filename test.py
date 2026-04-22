import torch
import sys

print(f"--- Diagnostic IA ---")
print(f"Version de Python : {sys.version}")
print(f"Version de PyTorch : {torch.__version__}")

try:
    # Test d'initialisation de la fameuse DLL c10
    x = torch.rand(5, 3)
    print("\n✅ Succès : PyTorch peut créer des tenseurs (DLL c10 OK).")
    
    # Test du GPU (si disponible)
    cuda_dispo = torch.cuda.is_available()
    print(f"Accélération GPU (CUDA) disponible : {cuda_dispo}")
    
    if cuda_dispo:
        print(f"Nom de la carte graphique : {torch.cuda.get_device_name(0)}")
        
except Exception as e:
    print(f"\n❌ Erreur détectée : {e}")
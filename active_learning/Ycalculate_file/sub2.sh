#!/bin/bash
#SBATCH --partition=v6_384  
#SBATCH --nodes=1        
#SBATCH --ntasks=24        
#SBATCH --output=%j.log     

#======================================================================
source /public5/soft/modules/module.sh  
module load mpi/oneAPI/2022.1  
export PATH=/public5/home/t6s008728/software-t6s008728/vasp.6.3.0/bin:$PATH
echo
echo
echo "=== VASP 版本检查 ==="
which vasp_std
vasp_std --version 2>&1 | grep -i version  
echo
echo
echo "=== 输入文件检查 ==="
ls -l INCAR KPOINTS POSCAR POTCAR  
echo
echo
#======================================================================
mpirun -np 24 vasp_std  

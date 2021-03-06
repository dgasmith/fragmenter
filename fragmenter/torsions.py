__author__ = 'Chaya D. Stern'

try:
    import openeye.oechem as oechem
except ImportError:
    pass
import warnings
import numpy as np
import itertools
from math import radians, degrees
import copy

from . import utils, chemi
from cmiles.utils import mol_to_smiles, has_atom_map, get_atom_map
from .utils import BOHR_2_ANGSTROM, logger
# warnings.simplefilter('always')


def find_torsions(molecule, restricted=True, terminal=True):
    """
    This function takes an OEMol (atoms must be tagged with index map) and finds the map indices for torsion that need
    to be driven.

    Parameters
    ----------
    molecule : OEMol
        The atoms in the molecule need to be tagged with map indices
    restricted: bool, optional, default True
        If True, will find restricted torsions such as torsions in rings and double bonds.
    terminal: bool, optional, default True
        If True, will find terminal torsions

    Returns
    -------
    needed_torsion_scans: dict
        a dictionary that maps internal, terminal and restricted torsions to map indices of torsion atoms

    """
    # Check if molecule has map
    is_mapped = has_atom_map(molecule)
    if not is_mapped:
        utils.logger().warning('Molecule does not have atom map. A new map will be generated. You might need a new tagged SMARTS if the ordering was changed')
        tagged_smiles = mol_to_smiles(molecule, isomeric=True, mapped=True, explicit_hydrogen=True)
        # Generate new molecule with tags
        molecule = chemi.smiles_to_oemol(tagged_smiles)
        utils.logger().warning('If you already have a tagged SMARTS, compare it with the new one to ensure the ordering did not change')
        utils.logger().warning('The new tagged SMARTS is: {}'.format(tagged_smiles))
        # ToDo: save the new tagged SMILES somewhere. Maybe return it?

    needed_torsion_scans = {'internal': {}, 'terminal': {}, 'restricted': {}}
    mol = oechem.OEMol(molecule)
    if restricted:
        smarts = '[*]~[C,c]=,@[C,c]~[*]' # This should capture double bonds (not capturing rings because OpenEye does not
                                       # generate skewed conformations. ToDo: use scan in geometric or something else to get this done.
        restricted_tors = _find_torsions_from_smarts(molecule=mol, smarts=smarts)
        if len(restricted_tors) > 0:
            restricted_tors_min = one_torsion_per_rotatable_bond(restricted_tors)
            for i, tor in enumerate(restricted_tors_min):
                tor_name = ((tor[0].GetMapIdx() - 1), (tor[1].GetMapIdx() - 1), (tor[2].GetMapIdx() - 1), (tor[3].GetMapIdx() - 1))
                needed_torsion_scans['restricted']['torsion_{}'.format(str(i))] = tor_name

    if terminal:
        smarts = '[*]~[*]-[X2H1,X3H2,X4H3]-[#1]' # This smarts should match terminal torsions such as -CH3, -NH2, -NH3+, -OH, and -SH
        h_tors = _find_torsions_from_smarts(molecule=mol, smarts=smarts)
        if len(h_tors) > 0:
            h_tors_min = one_torsion_per_rotatable_bond(h_tors)
            for i, tor in enumerate(h_tors_min):
                tor_name = ((tor[0].GetMapIdx() -1 ), (tor[1].GetMapIdx() - 1), (tor[2].GetMapIdx() - 1), (tor[3].GetMapIdx() - 1))
                needed_torsion_scans['terminal']['torsion_{}'.format(str(i))] = tor_name

    mid_tors = [[tor.a, tor.b, tor.c, tor.d ] for tor in oechem.OEGetTorsions(mol)]
    if mid_tors:
        mid_tors_min = one_torsion_per_rotatable_bond(mid_tors)
        for i, tor in enumerate(mid_tors_min):
            tor_name = ((tor[0].GetMapIdx() - 1), (tor[1].GetMapIdx() - 1), (tor[2].GetMapIdx() - 1), (tor[3].GetMapIdx() - 1))
            needed_torsion_scans['internal']['torsion_{}'.format(str(i))] = tor_name

    # Check that there are no duplicate torsions in mid and h_torsions
    list_tor = list(needed_torsion_scans['internal'].values()) + list(needed_torsion_scans['terminal'].values())
    set_tor = set(list_tor)

    if not len(set_tor) == len(list_tor):
        raise Warning("There is a torsion defined in both mid and terminal torsions. This should not happen. Check "
                      "your molecule and the atom mapping")
    return needed_torsion_scans


def _find_torsions_from_smarts(molecule, smarts):
    """
    Do a substrcutre search on provided SMARTS to find torsions that match the SAMRTS

    Parameters
    ----------
    molecule: OEMol
        molecule to search on
    smarts: str
        SMARTS pattern to search for

    Returns
    -------
    tors: list
        list of torsions that match the SMARTS string

    """

    #ToDO use MDL aromaticity model
    qmol=oechem.OEQMol()
    if not oechem.OEParseSmarts(qmol, smarts):
        utils.logger().warning('OEParseSmarts failed')
    ss = oechem.OESubSearch(qmol)
    tors = []
    oechem.OEPrepareSearch(molecule, ss)
    unique = True
    for match in ss.Match(molecule, unique):
        tor = []
        for ma in match.GetAtoms():
            tor.append(ma.target)
        tors.append(tor)

    return tors


def one_torsion_per_rotatable_bond(torsion_list):
    """
    Keep only one torsion per rotatable bond
    Parameters
    ----------
    torsion_list: list
        list of torsion in molecule

    Returns
    -------
    list of only one torsion per rotatable bonds

    """

    central_bonds = np.zeros((len(torsion_list), 3), dtype=int)
    for i, tor in enumerate(torsion_list):
        central_bonds[i][0] = i
        central_bonds[i][1] = tor[1].GetIdx()
        central_bonds[i][2] = tor[2].GetIdx()

    grouped = central_bonds[central_bonds[:, 2].argsort()]
    sorted_tors = [torsion_list[i] for i in grouped[:, 0]]

    # Keep only one torsion per rotatable bond
    tors = []
    best_tor = [sorted_tors[0][0], sorted_tors[0][0], sorted_tors[0][0], sorted_tors[0][0]]
    best_tor_order = best_tor[0].GetAtomicNum() + best_tor[3].GetAtomicNum()
    first_pass = True
    for tor in sorted_tors:
        utils.logger().debug("Map Idxs: {} {} {} {}".format(tor[0].GetMapIdx(), tor[1].GetMapIdx(), tor[2].GetMapIdx(), tor[3].GetMapIdx()))
        utils.logger().debug("Atom Numbers: {} {} {} {}".format(tor[0].GetAtomicNum(), tor[1].GetAtomicNum(), tor[2].GetAtomicNum(), tor[3].GetAtomicNum()))
        if tor[1].GetMapIdx() != best_tor[1].GetMapIdx() or tor[2].GetMapIdx() != best_tor[2].GetMapIdx():
            new_tor = True
            if not first_pass:
                utils.logger().debug("Adding to list: {} {} {} {}".format(best_tor[0].GetMapIdx(), best_tor[1].GetMapIdx(), best_tor[2].GetMapIdx(), best_tor[3].GetMapIdx()))
                tors.append(best_tor)
            first_pass = False
            best_tor = tor
            best_tor_order = tor[0].GetAtomicNum() + tor[3].GetAtomicNum()
            utils.logger().debug("new_tor with central bond across atoms: {} {}".format(tor[1].GetMapIdx(), tor[2].GetMapIdx()))
        else:
            utils.logger().debug("Not a new_tor but now with end atoms: {} {}".format(tor[0].GetMapIdx(), tor[3].GetMapIdx()))
            tor_order = tor[0].GetAtomicNum() + tor[3].GetAtomicNum()
            if tor_order > best_tor_order:
                best_tor = tor
                best_tor_order = tor_order
    utils.logger().debug("Adding to list: {} {} {} {}".format(best_tor[0].GetMapIdx(), best_tor[1].GetMapIdx(), best_tor[2].GetMapIdx(), best_tor[3].GetMapIdx()))
    tors.append(best_tor)

    utils.logger().info("List of torsion to drive:")
    for tor in tors:
        utils.logger().info("Idx: {} {} {} {}".format(tor[0].GetMapIdx(), tor[1].GetMapIdx(), tor[2].GetMapIdx(), tor[3].GetMapIdx()))
        utils.logger().info("Atom numbers: {} {} {} {}".format(tor[0].GetAtomicNum(), tor[1].GetAtomicNum(), tor[2].GetAtomicNum(), tor[3].GetAtomicNum()))

    return tors


def define_torsiondrive_jobs(needed_torsion_drives, internal_torsion_resolution=30, terminal_torsion_resolution=0,
                     scan_internal_terminal_combination=0, scan_dimension=2):
    """
    define crank jobs with torsions to drive and resolution to drive them at.

    Parameters
    ----------
    fragment_data: dict
        dictionary that maps fragment to needed torsions
    internal_torsion_resolution: int, optional. Default 15
        interval in degrees for torsion scan. If 0, internal torsions will not be driven
    terminal_torsion_resolution: int, optional. Default 0
        interval in degrees for torsion scans. If 0, terminal torsions will not be driven
    scan_internal_terminal_combination: int, optional. Default 0
        flag if internal and terminal torsions should be combined for higher dimension. If 0, only internal torsions will
        be driven. If 1, terminal and internal torsions will be scanned together.
    scan_dimension: int, optional. Default 2
        dimension of torsion scan. Combinations of torsions at the specified dimension will be generated as separate crank jobs
    qc_program: str, optional. Default Psi4
    method: str, optional. Default B3LYP
    basis: str, optional. Default aug-cc-pVDZ
    kwargs: optional keywords for psi4

    Returns
    -------
    fragment_data: dict
        dictionary that maps fragment to crank torsion jobs specifications.

    """

    if not internal_torsion_resolution and not terminal_torsion_resolution:
        utils.logger().warning("Resolution for internal and terminal torsions are 0. No torsions will be driven")

    if scan_internal_terminal_combination and (not internal_torsion_resolution or not terminal_torsion_resolution):
        raise Warning("If you are not scanning internal or terminal torsions, you must set scan_internal_terminal_"
                      "combinations to 0")

    internal_torsions = needed_torsion_drives['internal']
    terminal_torsions = needed_torsion_drives['terminal']
    internal_dimension = len(internal_torsions)
    terminal_dimension = len(terminal_torsions)
    torsion_dimension = internal_dimension + terminal_dimension

    crank_job = 0
    crank_jobs = dict()

    if not scan_internal_terminal_combination:
        if internal_torsion_resolution:
            for comb in itertools.combinations(internal_torsions, scan_dimension):
                dihedrals = [internal_torsions[torsion] for torsion in comb]
                grid = [internal_torsion_resolution]*len(dihedrals)
                crank_jobs['crank_job_{}'.format(crank_job)] = {'dihedrals': dihedrals, 'grid_spacing': grid}
                crank_job +=1
            if internal_dimension < scan_dimension and internal_dimension > 0:
                dihedrals = [internal_torsions[torsion] for torsion in internal_torsions]
                grid = [internal_torsion_resolution]*len(dihedrals)
                crank_jobs['crank_job_{}'.format(crank_job)] = {'dihedrals': dihedrals, 'grid_spacing': grid}
                crank_job +=1

        if terminal_torsion_resolution:
            for comb in itertools.combinations(terminal_torsions, scan_dimension):
                dihedrals = [terminal_torsions[torsion] for torsion in comb]
                grid = [terminal_torsion_resolution]*scan_dimension
                crank_jobs['crank_job_{}'.format(crank_job)] = {'dihedrals': dihedrals, 'grid_spacing': grid}
                crank_job +=1
            if terminal_dimension < scan_dimension and terminal_dimension > 0:
                dihedrals = [terminal_torsions[torsion] for torsion in terminal_torsions]
                grid = [terminal_torsion_resolution]*len(dihedrals)
                crank_jobs['crank_job_{}'.format(crank_job)] = {'dihedrals': dihedrals, 'grid_spacing': grid}
                crank_job +=1
    else:
        # combine both internal and terminal torsions
        all_torsion_idx = np.arange(0, torsion_dimension)
        for comb in itertools.combinations(all_torsion_idx, scan_dimension):
            internal_torsions = [internal_torsions['torsion_{}'.format(i)] for i in comb if i < internal_dimension]
            terminal_torsions = [terminal_torsions['torsion_{}'.format(i-internal_dimension)] for i in comb if i >= internal_dimension]
            grid = [internal_torsion_resolution]*len(internal_torsions)
            grid.extend([terminal_torsion_resolution]*len(terminal_torsions))
            dihedrals = internal_torsions + terminal_torsions
            crank_jobs['crank_job_{}'.format(crank_job)] = {'diherals': dihedrals, 'grid_spacing': grid}
            crank_job += 1
        if torsion_dimension < scan_dimension:
            internal_torsions = [internal_torsions['torsion_{}'.format(i)] for i in all_torsion_idx if i < internal_dimension]
            terminal_torsions = [terminal_torsions['torsion_{}'.format(i-internal_dimension)] for i in all_torsion_idx if i >= internal_dimension]
            grid = [internal_torsion_resolution]*len(internal_torsions)
            grid.extend([terminal_torsion_resolution]*len(terminal_torsions))
            dihedrals = internal_torsions + terminal_torsions
            crank_jobs['crank_job_{}'.format(crank_job)] = {'diherals': dihedrals, 'grid_spacing': grid}
            crank_job += 1

    return crank_jobs


def define_restricted_drive(qc_molecule, restricted_dihedrals, steps=6, maximum_rotation=30, scan_dimension=1):
    """

    Parameters
    ----------
    qc_molecule: molecule in QC_JSON format. This comes with a geometry, connectivity table, identifiers that also has
    a mapped SMILES so it can be checked.
    needed_torsion_drives
    grid_resolution
    maximum_rotation

    Returns
    -------

    """
    #ToDo extend to multi-dimensional scans
    #natoms = len(qc_molecule['symbols'])
    # Convert to 3D shape for
    #coords = np.array(qc_molecule['geometry'], dtype=float).reshape(natoms, 3) * utils.BOHR_2_ANGSTROM
    connectivity = np.asarray(qc_molecule['connectivity'])

    # Check dihedral indices are connected
    bond_tuples = list(zip(connectivity[:, :2].T[0], connectivity[:, :2].T[1]))
    optimization_jobs = {}
    i = 0
    for torsion in restricted_dihedrals:
        for a1, a2 in zip(restricted_dihedrals[torsion], restricted_dihedrals[torsion][1:]):
            if (a1, a2) not in bond_tuples and (a2, a1) not in bond_tuples:
                utils.logger().warning("torsion {} is not bonded. Skipping this torsion")
                continue
        # measure dihedral angle
        dihedral_angle = measure_dihedral_angle(restricted_dihedrals[torsion], qc_molecule['geometry'])
        t_tuple = restricted_dihedrals[torsion]
        angle = round(dihedral_angle)
        optimization_jobs['{}_{}'.format(t_tuple, i)] = {
            'type': 'optimization_input',
            'initial_molecule': qc_molecule,
            'dihedrals': [restricted_dihedrals[torsion]],
            'constraints': {'scan': [('dihedral', str(t_tuple[0]), str(t_tuple[1]), str(t_tuple[2]),
                                               str(t_tuple[3]), str(angle), str(angle + maximum_rotation),
                                               str(steps))]}}
        optimization_jobs['{}_{}'.format(t_tuple, i+1)] = {
            'type': 'optimization_input',
            'initial_molecule': qc_molecule,
            'dihedrals': [restricted_dihedrals[torsion]],
            'constraints': {'scan': [('dihedral', str(t_tuple[0]), str(t_tuple[1]), str(t_tuple[2]),
                                               str(t_tuple[3]), str(angle), str(angle - maximum_rotation),
                                               str(steps))]}}

    return optimization_jobs


def generate_constraint_opt_input(qc_molecule, dihedrals, maximum_rotation=30, interval=5, filename=None):
    """

    Parameters
    ----------
    qc_molecule
    dihedrals

    Returns
    -------
    QCFractal optimization jobs input

    """

    optimization_jobs = {}
    tagged_smiles = qc_molecule['identifiers']['canonical_isomeric_explicit_hydrogen_mapped_smiles']
    mol = oechem.OEMol()
    oechem.OESmilesToMol(mol, tagged_smiles)
    atom_map = get_atom_map(mol, tagged_smiles)

    coords = chemi.from_mapped_xyz_to_mol_idx_order(qc_molecule['geometry'], atom_map)

    # convert coord to Angstrom
    coords = coords * BOHR_2_ANGSTROM
    conf = mol.GetConfs().next()
    conf.SetCoords(oechem.OEFloatArray(coords))

    # new molecule for setting dihedral angles
    mol_2 = oechem.OEMol(mol)
    conf_2 = mol_2.GetConfs().next()
    coords_2 = oechem.OEFloatArray(conf_2.GetMaxAtomIdx()*3)
    conf.GetCoords(coords_2)
    mol_2.DeleteConfs()

    interval = radians(interval)
    max_rot = radians(maximum_rotation)
    for dihedral in dihedrals:
        j = 0
        dih_idx = dihedrals[dihedral]
        tor = []
        for i in dih_idx:
            a = mol.GetAtom(oechem.OEHasMapIdx(i+1))
            tor.append(a)
        dih_angle = oechem.OEGetTorsion(conf, tor[0], tor[1], tor[2], tor[3])
        for i, angle in enumerate(np.arange(dih_angle-max_rot, dih_angle+max_rot, interval)):
            newconf = mol.NewConf(coords_2)
            oechem.OESetTorsion(newconf, tor[0], tor[1], tor[2], tor[3], angle)
            new_angle = oechem.OEGetTorsion(newconf, tor[0], tor[1], tor[2], tor[3])
            # if new_angle == dih_angle:
            #     j += 1
            #     if j > 1:
            #         # One equivalent angle should be generated.
            #         logger().warning("Openeye did not generate a new conformer for torsion and angle {} {}. Will not generate"
            #                      "qcfractal optimizaiton input".format(dih_idx, angle))
            #         break
            if filename:
                pdb = oechem.oemolostream("{}_{}.pdb".format(filename, i))
                oechem.OEWritePDBFile(pdb, newconf)
            symbols, geometry = chemi.to_mapped_geometry(newconf, atom_map)
            qc_molecule = copy.deepcopy(qc_molecule)
            qc_molecule['geometry'] = geometry
            qc_molecule['symbols'] = symbols
            degree = degrees(angle)
            optimization_jobs['{}_{}'.format(dih_idx, int(round(degree)))] = {
                'type': 'optimization_input',
                'initial_molecule': qc_molecule,
                'dihedral': dih_idx,
                'constraints': {
                    "set": [{
                        "type": "dihedral",
                        "indices": dih_idx,
                        "value": degree
                    }]
                }
            }
    return optimization_jobs


def measure_dihedral_angle(dihedral, coords):
    """
    calculate the dihedral angle in degrees

    Parameters
    ----------
    dihedral
    coords

    Returns
    -------

    """
    coords = np.array(coords, dtype=float).reshape(int(len(coords)/3), 3) * utils.BOHR_2_ANGSTROM
    a = coords[dihedral[0]]
    b = coords[dihedral[1]]
    c = coords[dihedral[2]]
    d = coords[dihedral[3]]
    v1 = b-a
    v2 = c-b
    v3 = d-c
    t1 = np.linalg.norm(v2)*np.dot(v1, np.cross(v2, v3))
    t2 = np.dot(np.cross(v1, v2), np.cross(v2, v3))
    phi = np.arctan2(t1, t2)
    degree = phi * 180 / np.pi
    return degree


def find_equivelant_torsions(mapped_mol, restricted=False, central_bonds=None):
    """
    Final all torsions around a given central bond
    Parameters
    ----------
    mapped_mol: oemol. Must contaion map indices
    restricted: bool, optional, default False
        If True, will also find restricted torsions
    central_bonds: list of tuple of ints, optional, defualt None
        If provides, only torsions around those central bonds will be given. If None, all torsions in molecule will be found

    Returns
    -------
    eq_torsions: dict
        maps central bond to all equivelant torisons
    """
    #ToDo check that mol has mapping

    mol = oechem.OEMol(mapped_mol)
    if not has_atom_map(mol):
        raise ValueError("OEMol must have map indices")
    terminal_smarts = '[*]~[*]-[X2H1,X3H2,X4H3]-[#1]'
    terminal_torsions = _find_torsions_from_smarts(mol, terminal_smarts)
    mid_torsions = [[tor.a, tor.b, tor.c, tor.d] for tor in oechem.OEGetTorsions(mapped_mol)]
    all_torsions = terminal_torsions + mid_torsions
    if restricted:
        restricted_smarts = '[*]~[C,c]=,@[C,c]~[*]'
        restricted_torsions = _find_torsions_from_smarts(mol, restricted_smarts)
        all_torsions = all_torsions + restricted_torsions
    tor_idx = []
    for tor in all_torsions:
        tor_name = (tor[0].GetMapIdx()-1, tor[1].GetMapIdx()-1, tor[2].GetMapIdx()-1, tor[3].GetMapIdx()-1)
        tor_idx.append(tor_name)
    if central_bonds:
        if not isinstance(central_bonds, list):
            central_bonds = [central_bonds]
    if not central_bonds:
        central_bonds = set((tor[1], tor[2]) for tor in tor_idx)

    eq_torsions = {cb : [tor for tor in tor_idx if cb == (tor[1], tor[2]) or  cb ==(tor[2], tor[1])] for cb in
              central_bonds}
    return eq_torsions


def get_initial_crank_state(fragment):
    """
    Generate initial crank state JSON for each crank job in fragment
    Parameters
    ----------
    fragment: dict
        A fragment from JSON crank jobs

    Returns
    -------
    crank_initial_states: dict
        dictionary containing JSON specs for initial states for all crank jobs in a fragment.
    """
    crank_initial_states = {}
    init_geometry = fragment['molecule']['geometry']
    needed_torsions = fragment['needed_torsion_drives']
    crank_jobs = fragment['crank_torsion_drives']
    for i, job in enumerate(crank_jobs):
        dihedrals = []
        grid_spacing = []
        needed_mid_torsions = needed_torsions['internal']
        for mid_torsion in crank_jobs[job]['internal_torsions']:
            # convert 1-based indexing to 0-based indexing
            dihedrals.append([j-1 for j in needed_mid_torsions[mid_torsion]])
            grid_spacing.append(crank_jobs[job]['internal_torsions'][mid_torsion])
        needed_terminal_torsions = needed_torsions['terminal']
        for terminal_torsion in crank_jobs[job]['terminal_torsions']:
            # convert 1-based indexing to 0-based indexing
            dihedrals.append([j-1 for j in needed_terminal_torsions[terminal_torsion]])
            grid_spacing.append(crank_jobs[job]['terminal_torsions'][terminal_torsion])

        crank_state = {}
        crank_state['dihedrals'] = dihedrals
        crank_state['grid_spacing'] = grid_spacing
        crank_state['elements'] = fragment['molecule']['symbols']

        #ToDo add ability to start with many geomotries
        crank_state['init_coords'] = [init_geometry]
        crank_state['grid_status'] = {}

        crank_initial_states[job] = crank_state
    return crank_initial_states

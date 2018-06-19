""" Tests generating files for qm torsion scan """

import unittest
import json
from fragmenter.tests.utils import get_fn, has_openeye
import fragmenter.torsions as torsions
from fragmenter import utils
from openmoltools import openeye


class TestTorsions(unittest.TestCase):

    @unittest.skipUnless(has_openeye, 'Cannot test without openeye')
    def test_generate_torsions(self):
        """ Tests finding torsion to drive """
        from openeye import oechem
        infile = get_fn('butane.pdb')
        ifs = oechem.oemolistream(infile)
        inp_mol = oechem.OEMol()
        oechem.OEReadMolecule(ifs, inp_mol)
        needed_torsion_scans = torsions.find_torsions(molecule=inp_mol)
        self.assertEqual(len(needed_torsion_scans['mid'])-1, 1)
        self.assertEqual(len(needed_torsion_scans['terminal'])-1, 2)
        self.assertEqual(needed_torsion_scans['mid']['torsion_0'], (14, 10, 7, 4))
        self.assertEqual(needed_torsion_scans['terminal']['torsion_0'], (10, 7, 4, 3))
        self.assertEqual(needed_torsion_scans['terminal']['torsion_1'], (7, 10, 14, 13))

    @unittest.skipUnless(has_openeye, 'Cannot test without OpenEye')
    def test_tagged_smiles(self):
        """Test index-tagges smiles"""
        from openeye import oechem
        inf = get_fn('ethylmethylidyneamonium.mol2')
        ifs = oechem.oemolistream(inf)
        inp_mol = oechem.OEMol()
        oechem.OEReadMolecule(ifs, inp_mol)

        tagged_smiles = utils.create_mapped_smiles(inp_mol)

        # Tags should always be the same as mol2 molecule ordering
        self.assertEqual(tagged_smiles, '[H:5][C:1]#[N+:4][C:3]([H:9])([H:10])[C:2]([H:6])([H:7])[H:8]')

    @unittest.skipUnless(has_openeye, "Cannot test without OpneEye")
    def test_atom_map(self):
        """Test get atom map"""
        from openeye import oechem
        tagged_smiles = '[H:5][C:1]#[N+:4][C:3]([H:9])([H:10])[C:2]([H:6])([H:7])[H:8]'
        mol_1 = openeye.smiles_to_oemol('CC[N+]#C')
        inf = get_fn('ethylmethylidyneamonium.mol2')
        ifs = oechem.oemolistream(inf)
        mol_2 = oechem.OEMol()
        oechem.OEReadMolecule(ifs, mol_2)

        mol_1, atom_map = utils.get_atom_map(tagged_smiles, mol_1)

        for i, mapping in enumerate(atom_map):
            atom_1 = mol_1.GetAtom(oechem.OEHasAtomIdx(atom_map[mapping]))
            atom_1.SetAtomicNum(i+1)
            atom_2 = mol_2.GetAtom(oechem.OEHasAtomIdx(mapping-1))
            atom_2.SetAtomicNum(i+1)
            self.assertEqual(oechem.OECreateCanSmiString(mol_1), oechem.OECreateCanSmiString(mol_2))

        # Test aromatic molecule
        tagged_smiles = '[H:10][c:4]1[c:3]([c:2]([c:1]([c:6]([c:5]1[H:11])[H:12])[C:7]([H:13])([H:14])[H:15])[H:8])[H:9]'
        mol_1 = openeye.smiles_to_oemol('Cc1ccccc1')
        inf = get_fn('toluene.mol2')
        ifs = oechem.oemolistream(inf)
        mol_2 = oechem.OEMol()
        oechem.OEReadMolecule(ifs, mol_2)

        mol_1, atom_map = utils.get_atom_map(tagged_smiles, mol_1)
        for i, mapping in enumerate(atom_map):
            atom_1 = mol_1.GetAtom(oechem.OEHasAtomIdx(atom_map[mapping]))
            atom_1.SetAtomicNum(i+1)
            atom_2 = mol_2.GetAtom(oechem.OEHasAtomIdx(mapping-1))
            atom_2.SetAtomicNum(i+1)
            self.assertEqual(oechem.OECreateCanSmiString(mol_1), oechem.OECreateCanSmiString(mol_2))

    @unittest.skipUnless(has_openeye, "Cannot test without OpenEye")
    def test_atom_map_order(self):
        """Test atom map"""
        from openeye import oechem
        tagged_smiles = '[H:5][C:1]#[N+:4][C:3]([H:9])([H:10])[C:2]([H:6])([H:7])[H:8]'
        mol_from_tagged_smiles = openeye.smiles_to_oemol(tagged_smiles)
        mol_1, atom_map = utils.get_atom_map(tagged_smiles, mol_from_tagged_smiles)

        # Compare atom map to tag
        for i in range(1, len(atom_map) +1):
            atom_1 = mol_from_tagged_smiles.GetAtom(oechem.OEHasAtomIdx(atom_map[i]))
            self.assertEqual(i, atom_1.GetMapIdx())

    @unittest.skipUnless(has_openeye, "Cannot test without OpneEye")
    def test_mapped_xyz(self):
        """Test writing out mapped xyz"""
        from openeye import oechem, oeomega
        tagged_smiles = '[H:10][c:4]1[c:3]([c:2]([c:1]([c:6]([c:5]1[H:11])[H:12])[C:7]([H:13])([H:14])[H:15])[H:8])[H:9]'
        mol_1 = openeye.smiles_to_oemol('Cc1ccccc1')
        inf = get_fn('toluene.mol2')
        ifs = oechem.oemolistream(inf)
        mol_2 = oechem.OEMol()
        oechem.OEReadMolecule(ifs, mol_2)

        mol_1, atom_map = utils.get_atom_map(tagged_smiles, mol_1)
        for i, mapping in enumerate(atom_map):
            atom_1 = mol_1.GetAtom(oechem.OEHasAtomIdx(atom_map[mapping]))
            atom_1.SetAtomicNum(i+1)
            atom_2 = mol_2.GetAtom(oechem.OEHasAtomIdx(mapping-1))
            atom_2.SetAtomicNum(i+1)

        xyz_1 = utils.to_mapped_xyz(mol_1, atom_map)
        # molecule generated from mol2 should be in the right order.
        atom_map_mol2 = {1:0, 2:1, 3:2, 4:3, 5:4, 6:5, 7:6, 8:7, 9:8, 10:9, 11:10, 12:11, 13:12, 14:13, 15:14}
        xyz_2 = utils.to_mapped_xyz(mol_2, atom_map_mol2)

        for ele1, ele2 in zip(xyz_1.split('\n')[:-1], xyz_2.split('\n')[:-1]):
            self.assertEqual(ele1.split(' ')[2], ele2.split(' ')[2])

    @unittest.skipUnless(has_openeye, "Cannot test without OpenEye")
    def test_to_mapped_geometry(self):
        """Test mapped geometry"""
        from openeye import oechem

        infile = get_fn('butane.pdb')
        ifs = oechem.oemolistream(infile)
        molecule = oechem.OEMol()
        oechem.OEReadMolecule(ifs, molecule)
        tagged_smiles = utils.create_mapped_smiles(molecule)
        molecule, atom_map = utils.get_atom_map(tagged_smiles, molecule, is_mapped=True)
        mapped_geometry = utils.to_mapped_QC_JSON_geometry(molecule, atom_map)

        f = open(infile)
        line = f.readline()
        symbols = []
        geometry = []
        while line.strip():
            if line.startswith('ATOM'):
                line = line.split()
                symbols.append(line[2][0])
                geometry.append(line[5:8])
            line = f.readline()
        f.close()
        geometry = sum(geometry, [])
        self.assertEqual(symbols, mapped_geometry['symbols'])
        for x, y in zip(geometry, mapped_geometry['geometry']):
            self.assertAlmostEqual(float(x), y, 3)

    @unittest.skipUnless(has_openeye, "Cannot test without OpenEye")
    def test_crank_specs(self):
        """Test crank job JSON"""

        test_crank = {'canonical_isomeric_SMILES': 'CCCC',
                      'needed_torsion_drives': {'mid': {'grid_spacing': 30,
                                                        'torsion_0': (1, 2, 3, 4)},
                                                'terminal': {'grid_spacing': 30,
                                                             'torsion_0': (3, 2, 1, 5),
                                                             'torsion_1': (2, 3, 4, 12)}},
                      'provenance': {'canonicalization': 'openeye v2017.Oct.1',
                                     'package': 'fragmenter',
                                     'parent_molecule': 'CCCC',
                                     'routine': 'fragmenter.fragment.generate_fragments',
                                     'routine_options': {'MAX_ROTORS': 2,
                                                         'combinatorial': True,
                                                         'generate_visualization': False,
                                                         'json_filename': None,
                                                         'remove_map': True,
                                                         'strict_stereo': True},
                                     'user': 'chayastern',
                                     'version': '0.0.0+29.g7d02c4d.dirty'},
                      'tagged_SMARTS': '[H:5][C:1]([H:6])([H:7])[C:2]([H:8])([H:9])[C:3]([H:10])([H:11])[C:4]([H:12])([H:13])[H:14]'}

        crank_job = torsions.define_crank_job(test_crank)
        self.assertEqual(crank_job['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 30)
        self.assertEqual(crank_job['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_0'], 30)
        self.assertEqual(crank_job['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 30)

    def test_customize_grid(self):
        """Test more complicated grid structures"""

        json_file = open(get_fn('butane_crankjob.json'), 'r')
        test_crank_job = json.load(json_file)
        json_file.close()

        torsions.customize_grid_spacing(test_crank_job['CCCC'])
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions'], {'torsion_0': 15})
        self.assertFalse(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions'])

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=None, terminal_grid=None)
        with self.assertRaises(Warning):
            torsions.define_crank_job(test_crank_job['CCCC'])

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=None, terminal_grid=15)
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_0'], 15)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 15)
        self.assertFalse(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions'])

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=15, terminal_grid=[30, 60])
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_0'], 30)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 15)

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=None, terminal_grid=[30, 60])
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_0'], 30)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 60)
        self.assertFalse(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions'])

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=[[15], [30]], terminal_grid=None)
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertFalse(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 15)
        self.assertFalse(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['terminal_torsions'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['mid_torsions']['torsion_0'], 30)

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=[[15], [30]], terminal_grid=[[None, 30], [60, None]])
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 30)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 15)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['terminal_torsions']['torsion_0'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['mid_torsions']['torsion_0'], 30)

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=[[15], [30]], terminal_grid=60)
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_0'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['terminal_torsions']['torsion_1'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 15)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['terminal_torsions']['torsion_0'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['terminal_torsions']['torsion_1'], 60)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['mid_torsions']['torsion_0'], 30)

        torsions.customize_grid_spacing(test_crank_job['CCCC'], mid_grid=[[15], [None], [None]],
                                        terminal_grid=[[None, None], [15, None], [None, 15]])
        torsions.define_crank_job(test_crank_job['CCCC'])
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_0']['mid_torsions']['torsion_0'], 15)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_1']['terminal_torsions']['torsion_0'], 15)
        self.assertEqual(test_crank_job['CCCC']['crank_torsion_drives']['crank_job_2']['terminal_torsions']['torsion_1'], 15)

    def test_crank_initial_state(self):
        """ Test generate crank initial state"""
        jsonfile = open(get_fn('butane_crankjob.json'), 'r')
        test_crank_job = json.load(jsonfile)
        jsonfile.close()

        crank_initial_state = torsions.get_initial_crank_state(test_crank_job['CCCC'])
        for dihedral in crank_initial_state['crank_job_0']['dihedrals']:
            self.assertTrue(dihedral in [[2, 1, 0, 4], [0, 1, 2, 3], [1, 2, 3, 11]])
        self.assertEqual(crank_initial_state['crank_job_0']['grid_spacing'], [30, 30, 30])
        self.assertFalse(crank_initial_state['crank_job_0']['grid_status'])

    def test_formal_charge(self):
        """Test formal charge of molecule"""
        smiles = 'c1cc(c[nH+]c1)c2ccncn2'
        fragments = {'fragments':{'c1cc(c[nH+]c1)c2ccncn2': ['c1cc(c[nH+]c1)c2ccncn2',
                                                             'C[NH+]1CC[NH+](CC1)Cc2ccccc2']},
                     'provenance': {}}
        crank_job = torsions.fragment_to_torsion_scan(fragments)
        self.assertEqual(crank_job['c1cc(c[nH+]c1)c2ccncn2']['molecule']['molecular_charge'], 1)
        self.assertEqual(crank_job['C[NH+]1CC[NH+](CC1)Cc2ccccc2']['molecule']['molecular_charge'], 2)



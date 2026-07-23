import os
import unittest

import generate_pdf


class GeneratePdfCliTests(unittest.TestCase):
    def test_default_input_path_uses_workspace_xml(self):
        candidate = generate_pdf._default_input_path()
        self.assertTrue(candidate)
        self.assertTrue(os.path.exists(candidate))
        self.assertTrue(os.path.basename(candidate).endswith('.xml'))


if __name__ == '__main__':
    unittest.main()

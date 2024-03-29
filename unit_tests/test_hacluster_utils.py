import mock
import os
import re
import shutil
import tempfile
import unittest

import utils


def write_file(path, content, *args, **kwargs):
    with open(path, 'w') as f:
        f.write(content)
        f.flush()


@mock.patch.object(utils, 'log', lambda *args, **kwargs: None)
@mock.patch.object(utils, 'write_file', write_file)
class UtilsTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        utils.COROSYNC_CONF = os.path.join(self.tmpdir, 'corosync.conf')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @mock.patch.object(utils, 'get_ha_nodes', lambda *args: {'1': '10.0.0.1'})
    @mock.patch.object(utils, 'relation_get')
    @mock.patch.object(utils, 'related_units')
    @mock.patch.object(utils, 'relation_ids')
    @mock.patch.object(utils, 'get_network_address')
    @mock.patch.object(utils, 'config')
    def check_debug(self, enabled, mock_config, get_network_address,
                    relation_ids, related_units, relation_get):
        cfg = {'debug': enabled,
               'prefer-ipv6': False,
               'corosync_mcastport': '1234',
               'corosync_transport': 'udpu',
               'corosync_mcastaddr': 'corosync_mcastaddr'}

        def c(k):
            return cfg.get(k)

        mock_config.side_effect = c
        get_network_address.return_value = "127.0.0.1"
        relation_ids.return_value = ['foo:1']
        related_units.return_value = ['unit-machine-0']
        relation_get.return_value = 'iface'

        conf = utils.get_corosync_conf()

        if enabled:
            self.assertEqual(conf['debug'], enabled)
        else:
            self.assertFalse('debug' in conf)

        self.assertTrue(utils.emit_corosync_conf())

        with open(utils.COROSYNC_CONF) as fd:
            content = fd.read()
            if enabled:
                pattern = 'debug: on\n'
            else:
                pattern = 'debug: off\n'

            matches = re.findall(pattern, content, re.M)
            self.assertEqual(len(matches), 2, str(matches))

    def test_debug_on(self):
        self.check_debug(True)

    def test_debug_off(self):
        self.check_debug(False)

    @mock.patch.object(utils, 'config')
    def test_get_transport(self, mock_config):
        mock_config.return_value = 'udp'
        self.assertEqual('udp', utils.get_transport())

        mock_config.return_value = 'udpu'
        self.assertEqual('udpu', utils.get_transport())

        mock_config.return_value = 'hafu'
        self.assertRaises(ValueError, utils.get_transport)

    def test_nulls(self):
        self.assertEquals(utils.nulls({'a': '', 'b': None, 'c': False}),
                          ['a', 'b'])

    @mock.patch.object(utils, 'local_unit', lambda *args: 'hanode/0')
    @mock.patch.object(utils, 'get_ipv6_addr')
    @mock.patch.object(utils, 'get_host_ip')
    @mock.patch.object(utils.utils, 'is_ipv6', lambda *args: None)
    @mock.patch.object(utils, 'get_corosync_id', lambda u: "%s-cid" % (u))
    @mock.patch.object(utils, 'peer_ips', lambda *args, **kwargs:
                       {'hanode/1': '10.0.0.2'})
    @mock.patch.object(utils, 'unit_get')
    @mock.patch.object(utils, 'config')
    def test_get_ha_nodes(self, mock_config, mock_unit_get, mock_get_host_ip,
                          mock_get_ipv6_addr):
        mock_get_host_ip.side_effect = lambda host: host

        def unit_get(key):
            return {'private-address': '10.0.0.1'}.get(key)

        mock_unit_get.side_effect = unit_get

        def config(key):
            return {'prefer-ipv6': False}.get(key)

        mock_config.side_effect = config
        nodes = utils.get_ha_nodes()
        self.assertEqual(nodes, {'hanode/0-cid': '10.0.0.1',
                                 'hanode/1-cid': '10.0.0.2'})

        self.assertTrue(mock_get_host_ip.called)
        self.assertFalse(mock_get_ipv6_addr.called)

    @mock.patch.object(utils, 'local_unit', lambda *args: 'hanode/0')
    @mock.patch.object(utils, 'get_ipv6_addr')
    @mock.patch.object(utils, 'get_host_ip')
    @mock.patch.object(utils.utils, 'is_ipv6')
    @mock.patch.object(utils, 'get_corosync_id', lambda u: "%s-cid" % (u))
    @mock.patch.object(utils, 'peer_ips', lambda *args, **kwargs:
                       {'hanode/1': '2001:db8:1::2'})
    @mock.patch.object(utils, 'unit_get')
    @mock.patch.object(utils, 'config')
    def test_get_ha_nodes_ipv6(self, mock_config, mock_unit_get, mock_is_ipv6,
                               mock_get_host_ip, mock_get_ipv6_addr):
        mock_get_ipv6_addr.return_value = '2001:db8:1::1'
        mock_get_host_ip.side_effect = lambda host: host

        def unit_get(key):
            return {'private-address': '10.0.0.1'}.get(key)

        mock_unit_get.side_effect = unit_get

        def config(key):
            return {'prefer-ipv6': True}.get(key)

        mock_config.side_effect = config
        nodes = utils.get_ha_nodes()
        self.assertEqual(nodes, {'hanode/0-cid': '2001:db8:1::1',
                                 'hanode/1-cid': '2001:db8:1::2'})

        self.assertFalse(mock_get_host_ip.called)
        self.assertTrue(mock_get_ipv6_addr.called)

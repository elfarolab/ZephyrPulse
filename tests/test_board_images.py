import base64
import datetime as dt
import json
from unittest import TestCase
from unittest.mock import patch
from test_pulse import PulseTest
from board_images import publish, select, MAX_BYTES, detected_format, valid_raster
from intelligence import inventory, update_history, render_extra
from pulse import collect, render, UTC

# Valid tiny raster fixture, not an actual board photo.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jP1sAAAAASUVORK5CYII=')

class BoardImageTests(TestCase):
    setUp = PulseTest.setUp
    git = PulseTest.git
    put = PulseTest.put
    commit = PulseTest.commit

    def binary(self, path, data=PNG):
        target=self.repo/path; target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)

    def test_exact_names_folder_alias_and_ambiguous_shared_folder(self):
        f='boards/adafruit/metro_rp2350'; m='boards/test/shared'
        boards={'a':{'name':'adafruit_metro_rp2350','folder':f},'x':{'name':'x','folder':m},'y':{'name':'y','folder':m}}
        files={f+'/doc/metro_rp2350.webp':('a',100),f+'/doc/pinout.png':('b',50),m+'/doc/shared.webp':('c',100),m+'/doc/x.png':('d',100),m+'/doc/y.svg':('e',100),m+'/doc/y.png':('f',MAX_BYTES+1)}
        selected=select(boards,files)
        self.assertEqual(selected['a'][0],f+'/doc/metro_rp2350.webp')
        self.assertEqual(selected['x'][0],m+'/doc/x.png');self.assertNotIn('y',selected)
        files[f+'/doc/adafruit_metro_rp2350.png']=('g',100)
        self.assertEqual(select(boards,files)['a'][0],f+'/doc/adafruit_metro_rp2350.png')

    def test_board_specific_photo_suffix(self):
        folder='boards/test/kit'; boards={'x':{'name':'kit_board','folder':folder}}
        files={folder+'/kit_board_front.webp':('a',100),folder+'/doc/kit_board_pinout.png':('b',100)}
        self.assertEqual(select(boards,files)['x'][0],folder+'/kit_board_front.webp')
        self.assertEqual(select(boards,{folder+'/doc/kit_board_pinout.png':('b',100)}),{})

    def test_local_binary_reuse_and_stable_card(self):
        self.binary(self.board+'doc/kit.png');self.put(self.board+'doc/index.rst','.. zephyr:board:: kit\n')
        self.put('boards/test/virtual/board.yml','board:\n  name: virtual\n  socs:\n    - name: chip\n')
        self.binary('boards/test/virtual/doc/pinout.png')
        sha=self.commit('board pictures');now=dt.datetime.now(UTC);docs=self.root/'docs'
        def build(head):
            boards=inventory(self.g,head,self.db);collect(self.db,self.g,head,now,72)
            coverage=update_history(self.db,self.g,head,now,boards,90,0)
            images=publish(self.g,head,boards,docs)
            render(self.db,docs,now,72,'https://example.invalid/',boards=boards)
            render_extra(self.db,docs,now,head,boards,coverage,[],{'status':'disabled','items':[]},{},{},'https://example.invalid/',board_images=images)
            return boards,images
        boards,images=build(sha);key=next(k for k in boards if boards[k]['name']=='kit');vkey=next(k for k in boards if boards[k]['name']=='virtual')
        self.assertNotIn(vkey,images); image=images[key];file=docs/image['url'];self.assertEqual(file.read_bytes(),PNG)
        page=docs/'boards'/f"{boards[key]['slug']}.md";original=page.read_bytes();mtime=file.stat().st_mtime_ns
        self.assertIn(b'loading="lazy"',original);self.assertIn(b'Image source',original);self.assertIn(sha.encode(),original);self.assertIn(image['url'].encode(),original)
        self.assertIn('No upstream board image available',(docs/'boards'/f"{boards[vkey]['slug']}.md").read_text())
        from generators import build_site
        from test_generators import Fake
        site=build_site(self.root,Fake(),'https://example.invalid/');self.assertEqual((site/image['url']).read_bytes(),PNG)
        catalog=json.loads((docs/'intelligence.json').read_text());self.assertEqual(next(b for b in catalog['boards'] if b['id']==key)['image_url'],image['url'])
        self.put('doc/unrelated.rst','not board related');new=self.commit('unrelated documentation')
        with patch('board_images.read_blobs',return_value=iter(())) as reader:
            _,again=build(new);reader.assert_called_once();self.assertEqual(reader.call_args.args[1],[])
        self.assertEqual(images,again);self.assertEqual(file.stat().st_mtime_ns,mtime);self.assertEqual(page.read_bytes(),original)
        self.assertEqual(publish(self.g,new,boards,docs,False),{});self.assertFalse(file.exists())

    def test_image_warning_diagnostics_preserve_validation(self):
        pointer = b'version https://git-lfs.github.com/spec/v1\n' + b'oid sha256:' + b'a'*64 + b'\nsize 100\n'
        self.assertEqual(detected_format(pointer), 'Git LFS pointer')
        self.assertEqual(detected_format(PNG), 'png')
        self.assertFalse(valid_raster(PNG, 'webp'))
        self.assertFalse(valid_raster(pointer, 'png'))
        self.assertEqual(detected_format(b'not an image'), 'unknown/unsupported signature')
        self.binary(self.board+'doc/kit.webp', PNG)
        head=self.commit('mismatched image extension');boards=inventory(self.g,head)
        docs=self.root/'docs'
        with self.assertLogs(level='INFO') as logs:
            images=publish(self.g,head,boards,docs)
        self.assertIn('expected webp; detected png', '\n'.join(logs.output))
        image=next(iter(images.values())); self.assertTrue(image['url'].endswith('.png'))
        self.assertEqual((docs/image['url']).read_bytes(),PNG)
        with patch('board_images.read_blobs',return_value=iter(())) as reader:
            self.assertEqual(publish(self.g,head,boards,docs),images)
            self.assertEqual(reader.call_args.args[1],[])
        self.assertTrue(image['path'].endswith('.webp'))

    def test_bad_image_and_symlink_not_published(self):
        self.binary(self.board+'doc/kit.png',b'not an image')
        (self.repo/self.board/'doc/kit.webp').symlink_to('kit.png')
        head=self.commit('invalid image files');boards=inventory(self.g,head);docs=self.root/'docs'
        self.assertEqual(publish(self.g,head,boards,docs),{})
        self.assertEqual(list((docs/'data/board-images').iterdir()),[])

    def test_replaced_image_keeps_one_prior_catalog_generation(self):
        self.binary(self.board+'doc/kit.png');head=self.commit('image');boards=inventory(self.g,head);docs=self.root/'docs'
        first=publish(self.g,head,boards,docs);key=next(iter(boards));old=docs/first[key]['url']
        (docs/'intelligence.json').write_text(json.dumps({'boards':[{'image_url':first[key]['url']}]}))
        # Distinct valid raster signature; use GIF format instead of changing PNG.
        self.git('rm',self.board+'doc/kit.png');self.binary(self.board+'doc/kit.gif',base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'))
        new=self.commit('replace photo');second=publish(self.g,new,boards,docs)
        self.assertNotEqual(first,second);self.assertTrue(old.exists());self.assertTrue((docs/second[key]['url']).exists())
        (docs/'intelligence.json').write_text(json.dumps({'boards':[{'image_url':second[key]['url']}]}))
        publish(self.g,new,boards,docs);self.assertFalse(old.exists())

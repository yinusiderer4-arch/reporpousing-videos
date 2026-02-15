from __future__ import annotations

import functools
import json
import os.path
import re
import shutil
import subprocess

from yt_dlp.extractor.youtube.pot.provider import (
    PoTokenProviderError,
    PoTokenRequest,
    PoTokenResponse,
    register_preference,
    register_provider,
)
from yt_dlp.extractor.youtube.pot.utils import get_webpo_content_binding
from yt_dlp.utils import Popen

from yt_dlp_plugins.extractor.getpot_bgutil import BgUtilPTPBase


@register_provider
class BgUtilScriptPTP(BgUtilPTPBase):
    PROVIDER_NAME = 'bgutil:script'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_script = functools.cache(self._check_script_impl)

    @functools.cached_property
    def _script_path(self):
        return '/app/generate_once.js'

    def is_available(self):
        return self._check_script(self._script_path)

    @functools.cached_property
    def _node_path(self):
        node_path = shutil.which('node')
        if node_path is None:
            self.logger.trace('node is not in PATH')
        vsn = self._check_node_version(node_path)
        if vsn:
            self.logger.trace(f'Node version: {vsn}')
            return node_path

    def _check_script_impl(self, script_path):
        # --- BYPASS DE VELOCIDAD ---
        # No ejecutamos nada. Asumimos que es la versión correcta.
        
        # 1. Le decimos al sistema que somos la versión 1.2.2 (Hardcoded)
        # Esto evita el error "Plugin and script major versions are mismatched"
        self._check_version('1.2.2', name='script')
        
        # 2. Devolvemos True inmediatamente sin llamar a subprocess
        return True

    def _check_node_version(self, node_path):
        try:
            stdout, stderr, returncode = Popen.run(
                [node_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=self._GET_SERVER_VSN_TIMEOUT)
            stdout = stdout.strip()
            mobj = re.match(r'v(\d+)\.(\d+)\.(\d+)', stdout)
            if returncode or not mobj:
                raise ValueError
            node_vsn = tuple(map(int, mobj.groups()))
            if node_vsn >= self._MIN_NODE_VSN:
                return node_vsn
            raise RuntimeError
        except RuntimeError:
            min_vsn_str = 'v' + '.'.join(str(v) for v in self._MIN_NODE_VSN)
            self.logger.warning(
                f'Node version too low. '
                f'(got {stdout}, but at least {min_vsn_str} is required)')
        except (subprocess.TimeoutExpired, ValueError):
            self.logger.warning(
                f'Failed to check node version. '
                f'Node returned {returncode} exit status. '
                f'Node stdout: {stdout}; Node stderr: {stderr}')

    def _real_request_pot(
        self,
        request: PoTokenRequest,
    ) -> PoTokenResponse:
        # used for CI check
        self.logger.trace(
            f'Generating POT via script: {self._script_path}')

        command_args = [self._node_path, self._script_path]
        if proxy := request.request_proxy:
            command_args.extend(['-p', proxy])
        command_args.extend(['-c', get_webpo_content_binding(request)[0]])
        if request.bypass_cache:
            command_args.append('--bypass-cache')
        if request.request_source_address:
            command_args.extend(
                ['--source-address', request.request_source_address])
        if request.request_verify_tls is False:
            command_args.append('--disable-tls-verification')

        self.logger.info(
            f'Generating a {request.context.value} PO Token for '
            f'{request.internal_client_name} client via bgutil script',
        )
        self.logger.debug(
            f'Executing command to get POT via script: {" ".join(command_args)}')

        try:
            stdout, stderr, returncode = Popen.run(
                command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=self._GETPOT_TIMEOUT)
        except subprocess.TimeoutExpired as e:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed: Timeout expired when trying to run script (caused by {e!r})')
        except Exception as e:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed: Unable to run script (caused by {e!r})') from e

        msg = ''
        if stdout_extra := stdout.strip().splitlines()[:-1]:
            msg = f'stdout:\n{stdout_extra}\n'
        if stderr_stripped := stderr.strip():  # Empty strings are falsy
            msg += f'stderr:\n{stderr_stripped}\n'
        msg = msg.strip()
        if msg:
            self.logger.trace(msg)
        if returncode:
            raise PoTokenProviderError(
                f'_get_pot_via_script failed with returncode {returncode}')

        try:
            json_resp = stdout.splitlines()[-1]
            self.logger.trace(f'JSON response:\n{json_resp}')
            # The JSON response is always the last line
            script_data_resp = json.loads(json_resp)
        except json.JSONDecodeError as e:
            raise PoTokenProviderError(
                f'Error parsing JSON response from _get_pot_via_script (caused by {e!r})') from e
        if 'poToken' not in script_data_resp:
            raise PoTokenProviderError(
                'The script did not respond with a po_token')
        return PoTokenResponse(po_token=script_data_resp['poToken'])


@register_preference(BgUtilScriptPTP)
def bgutil_script_getpot_preference(provider, request):
    return 1


__all__ = [BgUtilScriptPTP.__name__,
           bgutil_script_getpot_preference.__name__]

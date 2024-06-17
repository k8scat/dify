import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from core.app.app_config.entities import AppAdditionalFeatures
from core.helper.encrypter import decrypt_token, encrypt_token, obfuscated_token
from extensions.ext_database import db
from models.model import App, AppModelConfig, Conversation, Message, TracingAppConfig
from models.workflow import Workflow
from services.ops_trace.langfuse_trace import LangFuseDataTrace
from services.ops_trace.langsmith_trace import LangSmithDataTrace


class TracingProviderEnum(Enum):
    LANGFUSE = 'langfuse'
    LANGSMITH = 'langSmith'


class LangfuseConfig(BaseModel):
    """
    Model class for Langfuse tracing config.
    """
    public_key: str
    secret_key: str
    host: str


class LangsmithConfig(BaseModel):
    """
    Model class for Langsmith tracing config.
    """
    api_key: str
    project: str
    endpoint: str


class OpsTraceService:
    @classmethod
    def get_tracing_app_config(cls, app_id: str, tracing_provider: str):
        """
        Get tracing app config
        :param app_id: app id
        :param tracing_provider: tracing provider
        :return:
        """
        trace_config_data: TracingAppConfig = db.session.query(TracingAppConfig).filter(
            TracingAppConfig.app_id == app_id, TracingAppConfig.tracing_provider == tracing_provider
        ).first()

        if not trace_config_data:
            return None

        # decrypt_token and obfuscated_token
        tenant_id = db.session.query(App).filter(App.id == app_id).first().tenant_id
        decrypt_tracing_config = cls.decrypt_tracing_config(tenant_id, tracing_provider, trace_config_data.tracing_config)
        decrypt_tracing_config = cls.obfuscated_decrypt_token(tracing_provider, decrypt_tracing_config)

        trace_config_data.tracing_config = decrypt_tracing_config

        return trace_config_data.to_dict()

    @classmethod
    def create_tracing_app_config(cls, app_id: str, tracing_provider: str, tracing_config: dict):
        """
        Create tracing app config
        :param app_id: app id
        :param tracing_provider: tracing provider
        :param tracing_config: tracing config
        :return:
        """
        # check if trace config already exists
        trace_config_data: TracingAppConfig = db.session.query(TracingAppConfig).filter(
            TracingAppConfig.app_id == app_id, TracingAppConfig.tracing_provider == tracing_provider
        ).first()

        if trace_config_data:
            return None

        # get tenant id
        tenant_id = db.session.query(App).filter(App.id == app_id).first().tenant_id
        tracing_config = cls.encrypt_tracing_config(tenant_id, tracing_provider, tracing_config)
        trace_config_data = TracingAppConfig(
            app_id=app_id,
            tracing_provider=tracing_provider,
            tracing_config=tracing_config,
        )
        db.session.add(trace_config_data)
        db.session.commit()

        return trace_config_data.to_dict()

    @classmethod
    def update_tracing_app_config(cls, app_id: str, tracing_provider: str, tracing_config: dict):
        """
        Update tracing app config
        :param app_id: app id
        :param tracing_provider: tracing provider
        :param tracing_config: tracing config
        :return:
        """
        # check if trace config already exists
        trace_config = db.session.query(TracingAppConfig).filter(
            TracingAppConfig.app_id == app_id, TracingAppConfig.tracing_provider == tracing_provider
        ).first()

        if not trace_config:
            return None

        # get tenant id
        tenant_id = db.session.query(App).filter(App.id == app_id).first().tenant_id
        tracing_config = cls.encrypt_tracing_config(tenant_id, tracing_provider, tracing_config)

        trace_config.tracing_config = tracing_config
        db.session.commit()

        return trace_config.to_dict()

    @classmethod
    def delete_tracing_app_config(cls, app_id: str, tracing_provider: str):
        """
        Delete tracing app config
        :param app_id: app id
        :param tracing_provider: tracing provider
        :return:
        """
        trace_config = db.session.query(TracingAppConfig).filter(
            TracingAppConfig.app_id == app_id, TracingAppConfig.tracing_provider == tracing_provider
        ).first()

        if not trace_config:
            return None

        db.session.delete(trace_config)
        db.session.commit()

        return True
    
    @classmethod
    def encrypt_tracing_config(cls, tenant_id: str, tracing_provider: str, tracing_config: dict):
        """
        Encrypt tracing config
        :param tenant_id: tenant id
        :param tracing_provider: tracing provider
        :param tracing_config: tracing config
        :return:
        """
        if tracing_provider == TracingProviderEnum.LANGFUSE.value:
            tracing_config = LangfuseConfig(**tracing_config)
            encrypt_public_key = encrypt_token(tenant_id, tracing_config.public_key)
            encrypt_secret_key = encrypt_token(tenant_id, tracing_config.secret_key)
            tracing_config = LangfuseConfig(
                public_key=encrypt_public_key,
                secret_key=encrypt_secret_key,
                host=tracing_config.host
            )
        elif tracing_provider == TracingProviderEnum.LANGSMITH.value:
            tracing_config = LangsmithConfig(**tracing_config)
            encrypt_api_key = encrypt_token(tenant_id, tracing_config.api_key)
            tracing_config = LangsmithConfig(
                api_key=encrypt_api_key,
                project=tracing_config.project,
                endpoint=tracing_config.endpoint
            )

        if isinstance(tracing_config, BaseModel):
            return tracing_config.dict()
        return tracing_config

    @classmethod
    def decrypt_tracing_config(cls, tenant_id: str, tracing_provider: str, tracing_config: dict):
        """
        Decrypt tracing config
        :param tenant_id: tenant id
        :param tracing_provider: tracing provider
        :param tracing_config: tracing config
        :return:
        """
        if tracing_provider == TracingProviderEnum.LANGFUSE.value:
            tracing_config = LangfuseConfig(**tracing_config)
            decrypt_public_key = decrypt_token(tenant_id, tracing_config.public_key)
            decrypt_secret_key = decrypt_token(tenant_id, tracing_config.secret_key)
            tracing_config = LangfuseConfig(
                public_key=decrypt_public_key,
                secret_key=decrypt_secret_key,
                host=tracing_config.host
            )
        elif tracing_provider == TracingProviderEnum.LANGSMITH.value:
            tracing_config = LangsmithConfig(**tracing_config)
            decrypt_api_key = decrypt_token(tenant_id, tracing_config.api_key)
            tracing_config = LangsmithConfig(
                api_key=decrypt_api_key,
                project=tracing_config.project,
                endpoint=tracing_config.endpoint
            )

        if isinstance(tracing_config, BaseModel):
            return tracing_config.dict()
        return tracing_config

    @classmethod
    def obfuscated_decrypt_token(cls, tracing_provider: str, decrypt_tracing_config:dict):
        """
        Decrypt tracing config
        :param tracing_provider: tracing provider
        :param decrypt_tracing_config: tracing config
        :return:
        """
        if tracing_provider == TracingProviderEnum.LANGFUSE.value:
            decrypt_tracing_config = LangfuseConfig(**decrypt_tracing_config)
            decrypt_public_key = decrypt_tracing_config.public_key
            decrypt_secret_key = decrypt_tracing_config.secret_key
            obfuscated_public_key = obfuscated_token(decrypt_public_key)
            obfuscated_secret_key = obfuscated_token(decrypt_secret_key)
            decrypt_tracing_config = LangfuseConfig(
                public_key=obfuscated_public_key,
                secret_key=obfuscated_secret_key,
                host=decrypt_tracing_config.host
            )
        elif tracing_provider == TracingProviderEnum.LANGSMITH.value:
            decrypt_tracing_config = LangsmithConfig(**decrypt_tracing_config)
            decrypt_api_key = decrypt_tracing_config.api_key
            obfuscated_api_key = obfuscated_token(decrypt_api_key)
            decrypt_tracing_config = LangsmithConfig(
                api_key=obfuscated_api_key,
                project=decrypt_tracing_config.project,
                endpoint=decrypt_tracing_config.endpoint
            )

        return decrypt_tracing_config.dict()

    @classmethod
    def get_decrypted_tracing_config(cls, app_id: str, tracing_provider: str):
        """
        Get decrypted tracing config
        :param app_id: app id
        :param tracing_provider: tracing provider
        :return:
        """
        trace_config_data: TracingAppConfig = db.session.query(TracingAppConfig).filter(
            TracingAppConfig.app_id == app_id, TracingAppConfig.tracing_provider == tracing_provider
        ).first()

        if not trace_config_data:
            return None

        # decrypt_token
        tenant_id = db.session.query(App).filter(App.id == app_id).first().tenant_id
        decrypt_tracing_config = cls.decrypt_tracing_config(
            tenant_id, tracing_provider, trace_config_data.tracing_config
        )

        return decrypt_tracing_config

    @classmethod
    def get_ops_trace_instance(
        cls,
        app_id: str,
        workflow: Optional[Workflow] = None,
        app_model_config: Optional[AppModelConfig | AppAdditionalFeatures] = None
    ):
        """
        Get ops trace through model config
        :param app_id: app_id
        :param workflow: workflow
        :param app_model_config: app_model_config
        :return:
        """
        tracing_instance = None
        app_ops_trace_config = None

        # get trace configuration from available sources
        if app_model_config is not None:
            if isinstance(app_model_config, AppAdditionalFeatures):
                app_ops_trace_config = app_model_config.trace_config
            elif isinstance(app_model_config, AppModelConfig):
                app_ops_trace_config = json.loads(
                    app_model_config.trace_config
                ) if app_model_config.trace_config else None
        elif workflow:
            features_data = json.loads(workflow.features)
            app_ops_trace_config = features_data.get('trace_config') if features_data else None
        else:
            # As a last resort, fetch from the database
            trace_config_data = db.session.query(AppModelConfig.trace_config).filter(
                AppModelConfig.app_id == app_id
            ).order_by(AppModelConfig.updated_at.desc()).first()
            if trace_config_data:
                app_ops_trace_config = json.loads(trace_config_data.trace_config)
            else:
                raise ValueError('Trace config not found')

        if app_ops_trace_config is not None:
            tracing_provider = app_ops_trace_config.get('tracing_provider')
        else:
            return None

        # decrypt_token
        decrypt_trace_config = cls.get_decrypted_tracing_config(app_id, tracing_provider)
        if app_ops_trace_config.get('enabled'):
            if tracing_provider == TracingProviderEnum.LANGFUSE.value:
                langfuse_client_public_key = decrypt_trace_config.get('public_key')
                langfuse_client_secret_key = decrypt_trace_config.get('secret_key')
                langfuse_host = decrypt_trace_config.get('host')
                tracing_instance = LangFuseDataTrace(
                    langfuse_client_public_key,
                    langfuse_client_secret_key,
                    langfuse_host,
                )
            elif tracing_provider == TracingProviderEnum.LANGSMITH.value:
                langsmith_api_key = decrypt_trace_config.get('api_key')
                langsmith_project = decrypt_trace_config.get('project')
                langsmith_endpoint = decrypt_trace_config.get('endpoint')
                print(langsmith_api_key, langsmith_project, langsmith_endpoint)
                tracing_instance = LangSmithDataTrace(
                    langsmith_api_key,
                    langsmith_project,
                    langsmith_endpoint,
                )

            return tracing_instance

        return None

    @classmethod
    def get_app_config_through_message_id(cls, message_id: str):
        app_model_config = None
        message_data = db.session.query(Message).filter(Message.id == message_id).first()
        conversation_id = message_data.conversation_id
        conversation_data = db.session.query(Conversation).filter(Conversation.id == conversation_id).first()

        if conversation_data.app_model_config_id:
            app_model_config = db.session.query(AppModelConfig).filter(
                AppModelConfig.id == conversation_data.app_model_config_id
            ).first()
        elif conversation_data.app_model_config_id is None and conversation_data.override_model_configs:
            app_model_config = conversation_data.override_model_configs

        return app_model_config
